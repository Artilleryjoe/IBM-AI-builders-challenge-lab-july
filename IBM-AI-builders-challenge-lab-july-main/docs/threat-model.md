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

## Boundary 6 — Post-Quantum Threat to Audit Record Integrity

**Description:** Decision records are protected by a cryptographic hash. A sufficiently
powerful quantum computer could theoretically attack the hash function, undermining the
tamper-evidence guarantee that is central to the DAL's accountability story.

**Quantum threat analysis:**

| Hash function | Classical security | Quantum security (Grover) | Status |
|---|---|---|---|
| SHA-256 | 256-bit | ~128-bit effective (halved by Grover's algorithm) | Vulnerable to harvest-now-decrypt-later |
| SHAKE-256 (XOF, SHA-3 family) | 256-bit | ~256-bit — XOF output length is not halved by Grover in the same way as fixed-output hashes | **Used by the DAL** |

**Why SHAKE-256:**

SHAKE-256 is an extendable output function (XOF) from the SHA-3 family, standardised by NIST under FIPS 202 (2015) and referenced in NIST's post-quantum cryptography guidance. Unlike SHA-256, SHAKE-256 does not use the Merkle-Damgard construction that Grover's algorithm most efficiently attacks. At a 256-bit output length, SHAKE-256 provides full quantum preimage resistance — the same 256-bit digest length, the same 64-character hex wire format, zero change to storage or transmission infrastructure.

**Implementation:** The DAL uses SHAKE-256 as its sole hash algorithm for all new records, declared via the `HASH_ALGORITHM = "SHAKE-256"` constant in `src/decision_record.py`. Every saved record includes a `hash_algorithm` field making it self-describing — if the algorithm is ever upgraded again, older records can still be verified against their original algorithm.

**Legacy compatibility:** The `compute_hash_for_dict()` method reads the `hash_algorithm` field from each record before recomputing. Records saved before the PQC upgrade (which would carry `"SHA-256"` or no `hash_algorithm` field) are verified using SHA-256, preserving backward compatibility of the audit log.

**Threats and mitigations:**

| Threat | Description | Mitigation |
|---|---|---|
| **Harvest now, attack later** | An adversary records `record_hash` values today and attempts to forge a colliding record once a cryptographically-relevant quantum computer exists. | SHAKE-256 provides ~256-bit quantum preimage resistance, making preimage attacks against stored hashes computationally infeasible even under quantum threat models. |
| **Algorithm agility gap** | A future NIST guidance revision deprecates SHAKE-256 in favour of a new algorithm. | The `hash_algorithm` field on each record enables per-record algorithm selection. Migrating to a new algorithm requires only a new branch in `compute_hash_for_dict()` — no schema migration needed. |
| **Signature absence** | The hash proves the record was not modified, but does not prove who created it. A quantum-capable adversary who can forge the analyst's identity could create a plausible record from scratch. | Non-repudiation requires a digital signature scheme. Post-quantum signature (CRYSTALS-Dilithium / ML-DSA under FIPS 204) is the recommended future upgrade path. |

**Future upgrade path — post-quantum digital signatures:**

The current implementation provides tamper-evidence (hash-based). The next hardening step
is non-repudiation (signature-based): each record signed by the analyst's private key
using ML-DSA (CRYSTALS-Dilithium, NIST FIPS 204). This would make it cryptographically
impossible to deny or forge a decision record, even against a quantum adversary.

The `hash_algorithm` field is already a placeholder for this extensibility —
a future `signature_algorithm` field and `record_signature` field follow the same
self-describing pattern.

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
- [x] Upgrade record hash from SHA-256 to SHAKE-256 (post-quantum-resilient) — **done**
- [ ] Add post-quantum digital signatures (ML-DSA / CRYSTALS-Dilithium, NIST FIPS 204)
