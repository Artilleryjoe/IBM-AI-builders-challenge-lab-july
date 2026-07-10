# Threat Model

## Scope

This threat model covers the MVP prototype of the Decision Assurance Layer. It identifies the key trust boundaries, adversarial abuse cases, and design mitigations relevant to a system that sits between an AI recommendation engine and human security decisions.

This is not a production security review. The MVP has no authentication, no network hardening, and no role separation. The threat model is here to demonstrate that these concerns have been identified, reasoned about, and — where appropriate — addressed in the design.

---

## Trust Boundaries

### Boundary 1 — AI Model Output

**Description:** The Granite model on IBM watsonx.ai generates a recommendation, reasoning, and confidence score based on a prompt constructed from the scenario fixture. The DAL trusts this output enough to present it to the analyst, but the analyst is never required to follow it.

**Threats:**

| Threat | Description | Mitigation |
|---|---|---|
| **Prompt injection** | A threat scenario containing adversarially crafted text could attempt to manipulate the model's output (e.g., a malicious log entry containing instructions to the model). | In the MVP, scenario content is from static trusted fixtures. In production, input sanitisation and prompt construction controls would be required. |
| **Overconfident output** | The model may return a high `confidence_score` for a recommendation it is actually uncertain about. | The confidence score is surfaced visually as a colour-coded badge (green / amber / red). Analysts are trained via the framework documentation that the score is model-reported, not externally verified. |
| **Hallucinated evidence** | The model may generate reasoning that references evidence not present in the original scenario. | The analyst workbench displays the raw evidence separately from the AI reasoning. Analysts can directly compare the AI's reasoning against the actual evidence to spot fabrications. |
| **Recommendation framing bias** | The model's choice of words in the recommendation and reasoning may unduly influence the analyst toward a particular action (automation bias). | The UI is designed to show evidence *before* the AI recommendation is shown. The mandatory rationale field requires the analyst to articulate their own reasoning independently. |

---

### Boundary 2 — Decision Record Integrity

**Description:** A `DecisionRecord` is created, hashed, and written to IBM Cloud Object Storage. The record is only as trustworthy as the process that creates it and the storage that holds it.

**Threats:**

| Threat | Description | Mitigation |
|---|---|---|
| **Record tampering post-save** | An adversary with COS bucket write access could overwrite a decision record to change the analyst action or AI recommendation it documents. | The SHA-256 `record_hash` is computed over all fields before saving. Any modification to any field produces a different hash. The original hash is known (displayed in the UI on save) and can be independently verified. |
| **Record deletion** | An adversary could delete records from the COS bucket entirely, removing evidence of a decision. | COS bucket versioning and Object Lock (WORM) policies can prevent deletion. In the MVP, this is documented as a production hardening step. |
| **Hash collision / substitution** | An adversary could craft a different record that produces the same SHA-256 hash. | SHA-256 collision resistance is considered computationally infeasible for practical purposes. |
| **Clock manipulation** | The `timestamp` is set by the application server. An adversary with server access could manipulate it. | In production, timestamps should be server-side and from a trusted time source (e.g. NTP-synchronized, or issued by the persistence layer). Documented as a hardening step. |

---

### Boundary 3 — Analyst Identity

**Description:** In the MVP, `analyst_id` is hardcoded as `"analyst_01"`. No authentication is present. In a real deployment, this is a critical trust boundary.

**Threats:**

| Threat | Description | Mitigation |
|---|---|---|
| **Analyst impersonation** | Without authentication, any user can submit a decision attributed to any analyst. | MVP explicitly documents this as out of scope. Production deployment would require SSO / LDAP integration and session-bound analyst identity. |
| **Coercion / social engineering** | An analyst could be pressured (by a manager, or by the AI's framing) to approve a decision they disagree with, then record a false rationale. | The rationale field is free text and visible in the audit log. Post-incident review can identify implausible or formulaic rationales. The framework encourages override as a first-class action, reducing the stigma of disagreeing with the AI. |

---

### Boundary 4 — Credential Handling

**Description:** The application reads IBM watsonx.ai and IBM COS credentials from environment variables (`.env` file via `python-dotenv`).

**Threats:**

| Threat | Description | Mitigation |
|---|---|---|
| **Credential exposure in repository** | `.env` file committed to version control exposes API keys. | `.gitignore` explicitly excludes `.env`. `.env.example` contains only placeholder values. README instructs users to never commit `.env`. |
| **Credential exposure in logs** | Error messages or debug output could print credential values. | The `watsonx_client` and `cos_client` modules do not log credential values. Environment variable names are logged at most, not their values. |

---

### Boundary 5 — Fallback Path

**Description:** When IBM credentials are absent or services unavailable, the system falls back to mock AI responses and local file storage.

**Threats:**

| Threat | Description | Mitigation |
|---|---|---|
| **Fallback used in production** | An operator deploys the system without credentials; it silently runs in mock mode, generating fake AI recommendations and storing records locally rather than to COS. | The UI displays a `Demo Mode` banner whenever the fallback is active. Production deployment guidance in the README should enforce credentials as required configuration. |

---

## Out-of-Scope for MVP

The following threats are acknowledged but explicitly out of scope for the MVP:

- **Network-level attacks** (TLS, API gateway security) — no network hardening in the MVP
- **Denial of service** — single-user demo; no rate limiting or resource quotas
- **Data exfiltration via model output** — no sensitive real data; fixtures are synthetic
- **Supply chain attacks on Python dependencies** — `requirements.txt` pinning recommended for production
- **SIEM/EDR integration threats** — the MVP uses static fixtures, not live telemetry feeds

---

## Production Hardening Checklist

Items to address before any production deployment:

- [ ] Implement analyst authentication (SSO / LDAP / IBM App ID)
- [ ] Enable COS bucket versioning and Object Lock (WORM) for immutable audit records
- [ ] Add input sanitisation for any scenario content sourced from live feeds
- [ ] Pin all Python dependencies with hash verification in `requirements.txt`
- [ ] Add server-side timestamping from a trusted time source
- [ ] Add TLS for all API calls (enforced by IBM SDK by default; verify in deployment)
- [ ] Add rate limit and timeout controls to the watsonx.ai client
- [ ] Replace hardcoded `analyst_id` with session-bound identity
