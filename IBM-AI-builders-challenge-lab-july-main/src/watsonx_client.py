"""
watsonx_client.py

Wraps the IBM watsonx.ai SDK to generate structured threat recommendations
from a Granite instruct model.

Public API
----------
generate_recommendation(scenario: dict) -> dict
    Returns a dict with keys:
        recommendation    str   "investigate" | "escalate" | "dismiss"
        confidence_score  float 0.0 – 1.0
        reasoning         str   plain-language explanation
        suggested_actions list  2–3 concrete action strings

generate_ranked_actions(scenario: dict) -> list[dict]
    Returns a ranked list of all three possible actions, each with:
        action            str   "investigate" | "escalate" | "dismiss"
        confidence_score  float 0.0 – 1.0
        reasoning         str   why this action scores as it does
        suggested_steps   list  2–3 specific steps for this action
    Sorted highest-confidence-first.

If IBM credentials are absent or the API call fails, falls back automatically
to mock responses so the demo works without live credentials.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL_ID = "ibm/granite-13b-instruct-v2"

_SYSTEM_PROMPT = """\
You are a senior cybersecurity analyst assistant embedded in a Security Operations Centre.
Your role is to analyse threat alert data and produce a structured recommendation for the
human analyst who will make the final decision.

You MUST respond with valid JSON only — no markdown fences, no preamble, no trailing text.

Return exactly this JSON structure:
{
  "recommendation": "<one of: investigate | escalate | dismiss>",
  "confidence_score": <float between 0.0 and 1.0>,
  "reasoning": "<2-4 sentence explanation of why you chose this recommendation>",
  "suggested_actions": ["<action 1>", "<action 2>", "<action 3>"]
}

Guidelines:
- "escalate": use when evidence strongly suggests active compromise or imminent harm
- "investigate": use when evidence is suspicious but not conclusive
- "dismiss": use when evidence is most consistent with a false positive or benign activity
- confidence_score must reflect genuine uncertainty — do not inflate it
- suggested_actions must be specific and actionable (not generic advice)
- reasoning must reference the actual evidence provided, not generalise
"""


def _build_user_prompt(scenario: dict) -> str:
    """Construct the user-turn prompt from a scenario fixture dict."""
    evidence_lines = "\n".join(
        f"  - {e}" for e in scenario.get("raw_evidence", [])
    )
    context = scenario.get("context", {})
    context_lines = "\n".join(
        f"  {k}: {v}" for k, v in context.items()
    ) if context else "  (none)"

    return f"""Analyse the following threat alert and return your recommendation as JSON.

Alert Title : {scenario.get('title', 'Unknown')}
Severity    : {scenario.get('severity', 'UNKNOWN')}
Alert Type  : {scenario.get('alert_type', 'Unknown')}
MITRE Tactic: {scenario.get('mitre_tactic', 'Unknown')}
Source IP   : {scenario.get('source_ip', 'N/A')}
Destination : {scenario.get('destination_ip', 'N/A')}
Timestamp   : {scenario.get('timestamp', 'N/A')}

Evidence:
{evidence_lines}

Additional Context:
{context_lines}

Respond with JSON only."""


# ---------------------------------------------------------------------------
# watsonx.ai client (lazy-initialised)
# ---------------------------------------------------------------------------

_model: Optional[object] = None
_demo_mode: bool = False


def _get_model():
    """
    Lazily initialise the watsonx.ai ModelInference client.
    Sets _demo_mode = True if credentials are missing or init fails.
    """
    global _model, _demo_mode

    if _model is not None or _demo_mode:
        return _model

    api_key = os.getenv("WATSONX_API_KEY", "").strip()
    project_id = os.getenv("WATSONX_PROJECT_ID", "").strip()
    url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").strip()

    if not api_key or not project_id:
        logger.warning(
            "[watsonx_client] WATSONX_API_KEY or WATSONX_PROJECT_ID not set — "
            "running in demo mode with mock responses."
        )
        _demo_mode = True
        return None

    try:
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

        credentials = Credentials(url=url, api_key=api_key)
        client = APIClient(credentials=credentials, project_id=project_id)

        _model = ModelInference(
            model_id=_MODEL_ID,
            api_client=client,
            params={
                GenParams.MAX_NEW_TOKENS: 512,
                GenParams.TEMPERATURE: 0.1,   # low temperature for structured output
                GenParams.STOP_SEQUENCES: [],
            },
        )
        logger.info("[watsonx_client] Granite model initialised successfully.")
        return _model

    except Exception as exc:
        logger.warning(
            "[watsonx_client] Failed to initialise watsonx.ai client (%s) — "
            "falling back to demo mode.", exc
        )
        _demo_mode = True
        return None


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_response(raw_text: str) -> dict:
    """
    Extract a valid JSON object from the model's raw text output.

    Granite may wrap JSON in markdown fences or add a preamble — strip those
    before parsing.  If parsing fails entirely, return a fallback dict.
    """
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", raw_text).strip()

    # Try to find the first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[watsonx_client] Could not parse model JSON response: %r", raw_text[:200])
        return _fallback_parse_error_response()

    # Normalise fields
    recommendation = str(data.get("recommendation", "investigate")).lower().strip()
    if recommendation not in ("investigate", "escalate", "dismiss"):
        recommendation = "investigate"

    try:
        confidence = float(data.get("confidence_score", 0.6))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.6

    reasoning = str(data.get("reasoning", "")).strip()
    actions = data.get("suggested_actions", [])
    if not isinstance(actions, list):
        actions = [str(actions)]
    actions = [str(a).strip() for a in actions if str(a).strip()][:3]

    return {
        "recommendation": recommendation,
        "confidence_score": confidence,
        "reasoning": reasoning,
        "suggested_actions": actions,
        "source": "watsonx",
    }


def _fallback_parse_error_response() -> dict:
    return {
        "recommendation": "investigate",
        "confidence_score": 0.5,
        "reasoning": (
            "The AI model returned a response that could not be parsed. "
            "Please review the raw evidence manually and apply independent judgment."
        ),
        "suggested_actions": [
            "Review the raw evidence entries manually",
            "Cross-reference with threat intelligence feeds",
            "Escalate to a senior analyst if uncertain",
        ],
        "source": "parse_error_fallback",
    }


# ---------------------------------------------------------------------------
# Mock / fallback responses (keyed by scenario alert_type)
# ---------------------------------------------------------------------------

_MOCK_RESPONSES: dict[str, dict] = {
    "Lateral Movement": {
        "recommendation": "escalate",
        "confidence_score": 0.87,
        "reasoning": (
            "The evidence shows a service account performing an SMB subnet sweep outside "
            "business hours, followed by successful authentication to multiple hosts and a "
            "credential dump attempt on a high-value finance workstation. This pattern is "
            "highly consistent with active lateral movement by a compromised account."
        ),
        "suggested_actions": [
            "Isolate source host 10.0.4.88 from the network immediately",
            "Revoke and reset the svc_backup service account credentials",
            "Deploy EDR hunt across 10.0.4.0/24 for PSEXESVC.exe and lsass access artefacts",
        ],
        "source": "mock",
    },
    "Ransomware Precursor": {
        "recommendation": "escalate",
        "confidence_score": 0.96,
        "reasoning": (
            "The sequence of PowerShell execution policy bypass, payload download from a "
            "known Tor exit node, shadow copy deletion, recovery disablement, and rapid "
            "file encryption with ransom note creation is definitive ransomware execution. "
            "Containment is urgent — the encryption is already in progress."
        ),
        "suggested_actions": [
            "Immediately isolate SRV-FILE-201 from all network segments",
            "Activate the ransomware incident response playbook and notify IR leadership",
            "Preserve forensic image of SRV-FILE-201 before any remediation",
        ],
        "source": "mock",
    },
    "Credential Stuffing / Authentication Anomaly": {
        "recommendation": "investigate",
        "confidence_score": 0.71,
        "reasoning": (
            "Three accounts authenticated successfully during a large credential stuffing "
            "spray, with one account immediately accessing sensitive files and another "
            "passing MFA suspiciously fast. This warrants urgent investigation — the "
            "accounts may be compromised, but the evidence is not yet conclusive enough "
            "to assume full breach without further analysis."
        ),
        "suggested_actions": [
            "Force immediate password reset and MFA re-enrolment for mwilliams, t.chen, and r.patel",
            "Review session activity for all three accounts over the last 24 hours",
            "Block source IP 198.51.100.73 at the perimeter firewall pending investigation",
        ],
        "source": "mock",
    },
    "Data Exfiltration": {
        "recommendation": "escalate",
        "confidence_score": 0.88,
        "reasoning": (
            "An employee serving notice transferred 4.7 GB of sensitive HR compensation "
            "and investigations data to an unregistered external S3 bucket using an "
            "unsigned portable tool not in the approved software inventory. The combination "
            "of departure context, data sensitivity, and unapproved tooling makes this a "
            "high-confidence insider data theft case."
        ),
        "suggested_actions": [
            "Suspend m.jensen's network access immediately pending investigation",
            "Issue a legal hold on m.jensen's workstation and request preservation of the S3 bucket",
            "Notify HR, Legal, and the DLP team — this may be a regulatory breach",
        ],
        "source": "mock",
    },
    "Business Email Compromise": {
        "recommendation": "escalate",
        "confidence_score": 0.94,
        "reasoning": (
            "All technical indicators confirm a BEC attempt: SPF/DKIM/DMARC failures, "
            "a typosquatted domain matching the CFO's name, and a high-value wire transfer "
            "request timed to coincide with the CFO's travel window. The AP contact has "
            "already replied, increasing the risk of transfer execution. Immediate "
            "intervention is required before the 2-hour deadline."
        ),
        "suggested_actions": [
            "Contact a.santos directly (phone, not email) and instruct them NOT to process the transfer",
            "Block the sender domain corp-example.co at the mail gateway",
            "Notify the CFO via out-of-band channel and file an IC3 complaint",
        ],
        "source": "mock",
    },
    "Privilege Escalation": {
        "recommendation": "escalate",
        "confidence_score": 0.89,
        "reasoning": (
            "A junior developer downloaded and executed an unsigned token manipulation tool "
            "that successfully impersonated a service account with admin rights across 14 "
            "servers. Domain enumeration was completed and a lateral movement attempt to "
            "production was blocked only by the host firewall — not by detection. The "
            "attacker has demonstrated capability and intent."
        ),
        "suggested_actions": [
            "Isolate SRV-DEV-112 and terminate all sessions for r.okonkwo immediately",
            "Revoke svc_deploy token on all 14 servers and rotate the service account credentials",
            "Audit all 14 servers for signs of successful WMI or remote execution in the last hour",
        ],
        "source": "mock",
    },
    "Supply Chain Attack": {
        "recommendation": "escalate",
        "confidence_score": 0.97,
        "reasoning": (
            "A malicious typosquatted package was installed across 4 CI runners, establishing "
            "reverse shells and exfiltrating AWS and GitHub credentials. The blast radius is "
            "wide — any pipeline that ran in the last 47 minutes may be affected. CI/CD "
            "compromise gives the attacker potential production deployment capability. "
            "This is a critical-severity incident requiring immediate IR activation."
        ),
        "suggested_actions": [
            "Immediately rotate all exposed secrets: AWS keys and GitHub tokens from all 4 runners",
            "Isolate all 4 affected CI runners and remove requests-plus from the internal mirror",
            "Audit all deployments triggered in the last 47 minutes for signs of tampering",
        ],
        "source": "mock",
    },
    "Insider Threat": {
        "recommendation": "investigate",
        "confidence_score": 0.66,
        "reasoning": (
            "A privileged user accessed a large volume of sensitive HR records far outside "
            "their normal baseline and role scope, using inherited privileges that should "
            "have been revoked. No exfiltration was detected, but the access pattern and "
            "the user's PIP status create a concerning picture. Confidence is moderate — "
            "there may be a legitimate operational reason not captured in available data."
        ),
        "suggested_actions": [
            "Revoke p.walsh's inherited DBA privileges immediately via access review",
            "Preserve a full audit log of the session for HR and Legal review",
            "Interview p.walsh's manager before any direct confrontation to establish context",
        ],
        "source": "mock",
    },
    "Command and Control - DNS Tunnelling": {
        "recommendation": "escalate",
        "confidence_score": 0.91,
        "reasoning": (
            "The DNS query volume (312x baseline), base32-encoded subdomain pattern, "
            "large TXT response payloads, and a recently registered C2 domain are definitive "
            "indicators of DNS tunnelling. The affected host contains active M&A due "
            "diligence materials — the potential data loss impact is severe. The covert "
            "channel has been active for at least 6 hours."
        ),
        "suggested_actions": [
            "Isolate WS-LEGAL-199 from the network immediately to sever the C2 channel",
            "Block all DNS queries to tunnel-c2.xyz at the recursive resolver",
            "Engage IR and Legal — M&A data exposure may trigger regulatory and contractual obligations",
        ],
        "source": "mock",
    },
    "Zero-Day Exploit Attempt": {
        "recommendation": "escalate",
        "confidence_score": 0.95,
        "reasoning": (
            "The evidence confirms successful exploitation: the web application process wrote "
            "and executed an ELF binary, a reverse shell was established, and attacker "
            "commands were observed before egress was blocked. A patch for the exploited "
            "vulnerability was available but not applied. The host is a customer-facing "
            "production system — this is an active breach requiring immediate containment."
        ),
        "suggested_actions": [
            "Take WEB-APP-PROD-01 offline immediately and redirect traffic to a clean standby instance",
            "Apply CVE-2025-XXXX patch to all instances before bringing any back online",
            "Preserve the core dump and /tmp/.x binary for forensic analysis and threat intel sharing",
        ],
        "source": "mock",
    },
}

_DEFAULT_MOCK = {
    "recommendation": "investigate",
    "confidence_score": 0.65,
    "reasoning": (
        "The alert contains indicators consistent with suspicious activity. "
        "A full manual review of the evidence is recommended before taking action."
    ),
    "suggested_actions": [
        "Review all evidence entries in detail",
        "Cross-reference source IP against threat intelligence",
        "Escalate to senior analyst if additional indicators are found",
    ],
    "source": "mock",
}


def fallback_mock_response(scenario: dict) -> dict:
    """Return a realistic hardcoded mock response based on the scenario's alert_type."""
    alert_type = scenario.get("alert_type", "")
    return dict(_MOCK_RESPONSES.get(alert_type, _DEFAULT_MOCK))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_recommendation(scenario: dict) -> dict:
    """
    Generate a structured AI recommendation for the given scenario.

    Parameters
    ----------
    scenario : dict
        A scenario fixture dict as loaded by scenario_loader.

    Returns
    -------
    dict with keys: recommendation, confidence_score, reasoning,
                    suggested_actions, source
    """
    model = _get_model()

    if model is None:
        # No credentials or init failed — use mock
        return fallback_mock_response(scenario)

    prompt = _build_user_prompt(scenario)
    full_prompt = f"{_SYSTEM_PROMPT}\n\nUser:\n{prompt}\n\nAssistant:"

    try:
        response = model.generate_text(prompt=full_prompt)
        return _parse_response(response)
    except Exception as exc:
        logger.warning(
            "[watsonx_client] API call failed (%s) — falling back to mock response.", exc
        )
        return fallback_mock_response(scenario)


def is_demo_mode() -> bool:
    """Return True if the client is running without live IBM credentials."""
    _get_model()   # ensure initialisation has run
    return _demo_mode


# ---------------------------------------------------------------------------
# Ranked actions — system prompt and mock data
# ---------------------------------------------------------------------------

_RANKED_SYSTEM_PROMPT = """\
You are a senior cybersecurity analyst assistant embedded in a Security Operations Centre.
Your role is to evaluate ALL THREE possible response actions for a threat alert and score
each one with an independent confidence value, so the human analyst can see the full
decision landscape — not just the top recommendation.

You MUST respond with valid JSON only — no markdown fences, no preamble, no trailing text.

Return exactly this JSON structure:
{
  "ranked_actions": [
    {
      "action": "escalate",
      "confidence_score": <float 0.0-1.0>,
      "reasoning": "<1-2 sentences explaining why escalate scores as it does for this alert>",
      "suggested_steps": ["<step 1>", "<step 2>", "<step 3>"]
    },
    {
      "action": "investigate",
      "confidence_score": <float 0.0-1.0>,
      "reasoning": "<1-2 sentences explaining why investigate scores as it does>",
      "suggested_steps": ["<step 1>", "<step 2>"]
    },
    {
      "action": "dismiss",
      "confidence_score": <float 0.0-1.0>,
      "reasoning": "<1-2 sentences explaining why dismiss scores as it does>",
      "suggested_steps": ["<step 1>"]
    }
  ]
}

Rules:
- All three actions must be present — do not omit any.
- confidence_scores must sum to approximately 1.0 across the three actions.
- Sort ranked_actions by confidence_score descending.
- suggested_steps must be specific to the actual evidence provided.
- reasoning must reference specific evidence entries, not generic statements.
"""

# Per-scenario ranked mock responses
_RANKED_MOCK: dict[str, list[dict]] = {
    "Lateral Movement": [
        {"action": "escalate",    "confidence_score": 0.87, "reasoning": "SMB sweep + credential dump + out-of-hours service account activity is a strong lateral movement signature requiring immediate IR.", "suggested_steps": ["Isolate 10.0.4.88 now", "Revoke svc_backup credentials", "EDR hunt for PSEXESVC.exe across /24"]},
        {"action": "investigate", "confidence_score": 0.11, "reasoning": "A small chance this is a misconfigured backup job — worth verifying svc_backup's scheduled tasks before full escalation.", "suggested_steps": ["Check svc_backup scheduled task history", "Verify with system owner"]},
        {"action": "dismiss",     "confidence_score": 0.02, "reasoning": "Credential dump on lsass.exe makes benign explanation extremely unlikely.", "suggested_steps": ["Do not dismiss without full investigation"]},
    ],
    "Ransomware Precursor": [
        {"action": "escalate",    "confidence_score": 0.96, "reasoning": "File encryption is already in progress and shadow copies have been deleted — this is active ransomware, not a precursor.", "suggested_steps": ["Isolate SRV-FILE-201 immediately", "Activate ransomware IR playbook", "Preserve forensic image"]},
        {"action": "investigate", "confidence_score": 0.03, "reasoning": "Near-zero probability that vssadmin deletion + mass .enc renames is a false positive.", "suggested_steps": ["Do not delay for investigation — act now"]},
        {"action": "dismiss",     "confidence_score": 0.01, "reasoning": "Ransom note creation and C2 check-in make dismissal indefensible.", "suggested_steps": ["Do not dismiss"]},
    ],
    "Credential Stuffing / Authentication Anomaly": [
        {"action": "investigate", "confidence_score": 0.71, "reasoning": "Three successful authentications during a spray with anomalous post-login behaviour requires account-level investigation before assuming full breach.", "suggested_steps": ["Review session logs for mwilliams, t.chen, r.patel", "Check MFA push timing for t.chen", "Interview account holders"]},
        {"action": "escalate",    "confidence_score": 0.23, "reasoning": "If mwilliams' file access or t.chen's MFA fatigue is confirmed, immediate escalation to IR is warranted.", "suggested_steps": ["Force password reset for all three accounts", "Block source IP 198.51.100.73", "Notify IR team on standby"]},
        {"action": "dismiss",     "confidence_score": 0.06, "reasoning": "1,240 failed attempts followed by three successes is not consistent with routine user behaviour.", "suggested_steps": ["Do not dismiss without reviewing session data"]},
    ],
    "Data Exfiltration": [
        {"action": "escalate",    "confidence_score": 0.88, "reasoning": "4.7 GB of HR investigation data transferred to an unregistered bucket by a departing employee using unapproved tooling is a near-certain insider theft case.", "suggested_steps": ["Suspend m.jensen access", "Legal hold on workstation and S3 bucket", "Notify HR, Legal, DLP team"]},
        {"action": "investigate", "confidence_score": 0.10, "reasoning": "A small chance m.jensen was performing an authorised backup to a personal account — verify with HR before legal action.", "suggested_steps": ["Contact m.jensen's manager", "Check if any backup authorisation exists"]},
        {"action": "dismiss",     "confidence_score": 0.02, "reasoning": "Unsigned rclone.exe targeting compensation and active investigations data at end of tenure has no benign explanation.", "suggested_steps": ["Do not dismiss"]},
    ],
    "Business Email Compromise": [
        {"action": "escalate",    "confidence_score": 0.94, "reasoning": "SPF/DKIM/DMARC failure + typosquatted CFO domain + $187k request during confirmed travel window is a textbook BEC. AP has already replied.", "suggested_steps": ["Call a.santos now — do not process transfer", "Block corp-example.co at gateway", "File IC3 report"]},
        {"action": "investigate", "confidence_score": 0.05, "reasoning": "Extremely low probability this is a legitimate request given all technical indicators failing.", "suggested_steps": ["Verify directly with CFO via known phone number"]},
        {"action": "dismiss",     "confidence_score": 0.01, "reasoning": "All authentication headers confirm this is not from the corporate mail server.", "suggested_steps": ["Do not dismiss"]},
    ],
    "Privilege Escalation": [
        {"action": "escalate",    "confidence_score": 0.89, "reasoning": "Token impersonation succeeded, domain enumeration completed, and lateral movement to production was attempted — attacker has demonstrated capability.", "suggested_steps": ["Isolate SRV-DEV-112", "Revoke svc_deploy on all 14 servers", "Audit production servers for WMI artefacts"]},
        {"action": "investigate", "confidence_score": 0.09, "reasoning": "Possible the developer was running a misconfigured pentest tool — verify with the security team before assuming malicious intent.", "suggested_steps": ["Interview r.okonkwo immediately", "Check whether a pentest was scheduled"]},
        {"action": "dismiss",     "confidence_score": 0.02, "reasoning": "ImpersonateLoggedOnUser + domain enumeration is not a legitimate developer workflow.", "suggested_steps": ["Do not dismiss"]},
    ],
    "Supply Chain Attack": [
        {"action": "escalate",    "confidence_score": 0.97, "reasoning": "Reverse shells established, AWS/GitHub secrets exfiltrated across 4 runners — this is an active supply chain breach with production deployment blast radius.", "suggested_steps": ["Rotate all secrets immediately", "Isolate all 4 CI runners", "Audit last 47 minutes of deployments"]},
        {"action": "investigate", "confidence_score": 0.02, "reasoning": "Essentially zero probability that a post-install hook establishing a reverse shell is anything other than malicious.", "suggested_steps": ["Do not delay — rotate secrets while investigating"]},
        {"action": "dismiss",     "confidence_score": 0.01, "reasoning": "Exfiltrated credentials make dismissal impossible to justify.", "suggested_steps": ["Do not dismiss"]},
    ],
    "Insider Threat": [
        {"action": "investigate", "confidence_score": 0.66, "reasoning": "No exfiltration detected and there may be a legitimate operational reason for the access — investigation is warranted before confrontation.", "suggested_steps": ["Revoke DBA privileges immediately", "Preserve session audit log", "Consult HR and Legal before contacting p.walsh"]},
        {"action": "escalate",    "confidence_score": 0.27, "reasoning": "If the investigation confirms intent, rapid escalation to HR and Legal is required given the PIP context.", "suggested_steps": ["Prepare escalation brief for HR and Legal", "Ensure forensic preservation is complete"]},
        {"action": "dismiss",     "confidence_score": 0.07, "reasoning": "14x baseline access to sensitive HR records outside business hours is not consistent with routine work.", "suggested_steps": ["Do not dismiss without explanation from account holder"]},
    ],
    "Command and Control - DNS Tunnelling": [
        {"action": "escalate",    "confidence_score": 0.91, "reasoning": "312x DNS query baseline, base32-encoded subdomains, and a fresh C2 domain on an M&A host is definitive tunnelling — 6 hours of potential data loss.", "suggested_steps": ["Isolate WS-LEGAL-199 immediately", "Block tunnel-c2.xyz at resolver", "Engage IR and Legal for M&A data breach assessment"]},
        {"action": "investigate", "confidence_score": 0.07, "reasoning": "Very small chance this is a misconfigured DNS-based monitoring tool — check with the M&A team.", "suggested_steps": ["Verify with legal team if any DNS monitoring tools are deployed", "Isolate while investigating"]},
        {"action": "dismiss",     "confidence_score": 0.02, "reasoning": "9,847 TXT queries to a 11-day-old domain with base32-encoded subdomains has no benign explanation.", "suggested_steps": ["Do not dismiss"]},
    ],
    "Zero-Day Exploit Attempt": [
        {"action": "escalate",    "confidence_score": 0.95, "reasoning": "Successful exploitation confirmed — reverse shell established, attacker commands observed, ELF dropper written to disk. Patch was available 18h ago.", "suggested_steps": ["Take WEB-APP-PROD-01 offline immediately", "Apply CVE-2025-XXXX patch before restart", "Preserve core dump and /tmp/.x for forensics"]},
        {"action": "investigate", "confidence_score": 0.04, "reasoning": "Extremely low probability given confirmed post-exploitation artefacts.", "suggested_steps": ["Do not investigate in place — isolate first, then investigate"]},
        {"action": "dismiss",     "confidence_score": 0.01, "reasoning": "Node_app writing and executing an ELF binary is impossible to dismiss as benign.", "suggested_steps": ["Do not dismiss"]},
    ],
}

_DEFAULT_RANKED_MOCK = [
    {"action": "investigate", "confidence_score": 0.65, "reasoning": "Alert contains suspicious indicators that warrant investigation before escalation.", "suggested_steps": ["Review all evidence entries", "Cross-reference source IP against threat intel"]},
    {"action": "escalate",    "confidence_score": 0.25, "reasoning": "If investigation confirms malicious activity, escalation to IR is the next step.", "suggested_steps": ["Prepare IR brief", "Notify SOC manager"]},
    {"action": "dismiss",     "confidence_score": 0.10, "reasoning": "Dismissal is only appropriate if investigation confirms a false positive.", "suggested_steps": ["Document reason for dismissal if chosen"]},
]


def _parse_ranked_response(raw_text: str) -> list[dict]:
    """Parse a ranked_actions JSON response from the model."""
    text = re.sub(r"```(?:json)?", "", raw_text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
        actions = data.get("ranked_actions", [])
    except json.JSONDecodeError:
        logger.warning("[watsonx_client] Could not parse ranked response: %r", raw_text[:200])
        return _DEFAULT_RANKED_MOCK

    normalised = []
    valid_actions = {"investigate", "escalate", "dismiss"}
    for item in actions:
        action = str(item.get("action", "investigate")).lower().strip()
        if action not in valid_actions:
            continue
        try:
            score = float(item.get("confidence_score", 0.33))
            score = max(0.0, min(1.0, score))
        except (TypeError, ValueError):
            score = 0.33
        steps = item.get("suggested_steps", [])
        if not isinstance(steps, list):
            steps = [str(steps)]
        steps = [str(s).strip() for s in steps if str(s).strip()][:3]
        normalised.append({
            "action": action,
            "confidence_score": score,
            "reasoning": str(item.get("reasoning", "")).strip(),
            "suggested_steps": steps,
        })

    if not normalised:
        return _DEFAULT_RANKED_MOCK

    # Sort highest confidence first
    normalised.sort(key=lambda x: x["confidence_score"], reverse=True)
    return normalised


def fallback_ranked_mock(scenario: dict) -> list[dict]:
    """Return per-scenario ranked action mock data."""
    alert_type = scenario.get("alert_type", "")
    return list(_RANKED_MOCK.get(alert_type, _DEFAULT_RANKED_MOCK))


def generate_ranked_actions(scenario: dict) -> list[dict]:
    """
    Generate a ranked list of all three response actions for a scenario.

    Each action has its own confidence score, reasoning, and suggested steps,
    allowing the analyst to see the full decision landscape rather than only
    the top recommendation.

    Parameters
    ----------
    scenario : dict
        A scenario fixture dict as loaded by scenario_loader.

    Returns
    -------
    list[dict]
        List of 3 dicts sorted by confidence_score descending, each with keys:
        action, confidence_score, reasoning, suggested_steps.
    """
    model = _get_model()
    if model is None:
        return fallback_ranked_mock(scenario)

    prompt = _build_user_prompt(scenario)
    full_prompt = f"{_RANKED_SYSTEM_PROMPT}\n\nUser:\n{prompt}\n\nAssistant:"

    try:
        response = model.generate_text(prompt=full_prompt)
        return _parse_ranked_response(response)
    except Exception as exc:
        logger.warning(
            "[watsonx_client] Ranked actions API call failed (%s) — using mock.", exc
        )
        return fallback_ranked_mock(scenario)
