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

If IBM credentials are absent or the API call fails, falls back automatically
to fallback_mock_response(scenario) so the demo works without live credentials.
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
