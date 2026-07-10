# Decision Assurance Layer for AI-Assisted Cybersecurity

> **IBM AI Builders Challenge — July Wildcard**

## Thesis

> *Future cybersecurity is not AI autonomy. Future cybersecurity is accountable AI-assisted command and control.*

---

## What This Is

The **Decision Assurance Layer (DAL)** is a prototype that inserts a structured accountability checkpoint between AI-generated threat recommendations and human SOC analyst decisions.

The AI analyses the alert. The analyst reviews the evidence and AI output side-by-side. They make an explicit **Approve / Reject / Override** decision with a documented rationale. An immutable, SHA-256-hashed `DecisionRecord` is saved to IBM Cloud Object Storage.

Every record captures five elements — none are optional:

| Element | Description |
|---|---|
| **Evidence Bundle** | Raw timestamped threat data (EDR, auth, network, proxy logs) |
| **AI Recommendation** | Action recommended by IBM watsonx.ai (Granite) with reasoning |
| **Uncertainty Score** | Confidence score (0.0–1.0) visualised as a colour-coded badge |
| **Human Judgment** | Analyst action + mandatory rationale (approve / reject / override) |
| **Audit Record** | SHA-256-hashed `DecisionRecord` persisted to IBM Cloud Object Storage |

---

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url>
cd IBM-AI-builders-challenge-lab-july-main

# 2. Install dependencies (Python 3.10+)
pip install -r requirements.txt

# 3. Configure credentials (optional — demo mode works without them)
cp .env.example .env
# Edit .env with your IBM credentials

# 4. Run
streamlit run app.py
```

Open **http://localhost:8501**.

**No IBM credentials?** The app runs in Demo Mode automatically — mock AI responses and local file storage replace the live IBM services. The full workflow works end-to-end.

---

## Scenario Library (10 Scenarios)

| # | Scenario | Severity | MITRE Tactic |
|---|---|---|---|
| 001 | Lateral Movement via SMB — Internal Subnet Sweep | HIGH | TA0008 Lateral Movement |
| 002 | Ransomware Precursor — Shadow Copy Deletion | CRITICAL | TA0040 Impact |
| 003 | Credential Stuffing — VPN Gateway Anomaly | MEDIUM | TA0006 Credential Access |
| 004 | Data Exfiltration — Departing Employee to Cloud Storage | HIGH | TA0010 Exfiltration |
| 005 | Business Email Compromise — CFO Wire Transfer Request | CRITICAL | TA0043 Reconnaissance |
| 006 | Privilege Escalation — Token Impersonation | HIGH | TA0004 Privilege Escalation |
| 007 | Supply Chain Attack — Malicious PyPI Package in CI/CD | CRITICAL | TA0001 Initial Access |
| 008 | Insider Threat — Privileged Access Outside Role | MEDIUM | TA0009 Collection |
| 009 | DNS Tunnelling — Covert C2 via TXT Queries | HIGH | TA0011 Command and Control |
| 010 | Zero-Day Exploit — Memory Corruption RCE | CRITICAL | TA0002 Execution |

---

## IBM Credential Setup

Copy `.env.example` to `.env` and fill in your values. **Never commit `.env` to version control.**

| Variable | Where to find it |
|---|---|
| `WATSONX_API_KEY` | IBM Cloud → IAM → API Keys |
| `WATSONX_PROJECT_ID` | watsonx.ai → Your project → Manage → General |
| `WATSONX_URL` | `https://us-south.ml.cloud.ibm.com` (Dallas default) |
| `COS_API_KEY` | IBM Cloud → Cloud Object Storage → Service credentials |
| `COS_INSTANCE_CRN` | IBM Cloud → Cloud Object Storage → Resource Instance ID |
| `COS_ENDPOINT` | IBM Cloud → Cloud Object Storage → Endpoints |
| `COS_BUCKET_NAME` | Name of a pre-created bucket in your COS instance |

> **COS prerequisite:** The bucket named in `COS_BUCKET_NAME` must already exist before running the app.

---

## Architecture

```
Scenario Fixtures (data/scenarios/*.json)
           |
           v
    dal_engine.py  <-->  watsonx_client.py  -->  IBM watsonx.ai (Granite)
           |                                      [fallback: mock response]
           v
    Streamlit UI (app.py)
           |
           v
     cos_client.py  -->  IBM Cloud Object Storage  (decisions/{id}.json)
                         [fallback: data/decisions/]
```

Both IBM services degrade gracefully — the app runs fully offline with mock responses and local storage when credentials are absent.

---

## File Structure

```
.
├── app.py                              # Streamlit analyst workbench
├── requirements.txt                    # Python dependencies
├── .env.example                        # Credential template (copy to .env)
├── mvp-plan.md                         # Implementation plan (all tasks complete)
├── docs/
│   ├── concept.md                      # What the DAL is and why
│   ├── problem-statement.md            # The accountability gap being addressed
│   ├── decision-assurance-framework.md # The five-element framework
│   ├── architecture-draft.md           # Component diagram and data flow
│   ├── threat-model.md                 # Trust boundaries and mitigations
│   ├── user-stories.md                 # Analyst and auditor user stories
│   ├── ibm-bob-usage-plan.md           # How IBM Bob was used in this project
│   └── judging-criteria-map.md         # Judging criteria mapped to artefacts
├── data/
│   └── scenarios/                      # 10 threat scenario fixtures (JSON)
└── src/
    ├── scenario_loader.py              # Loads scenario fixtures
    ├── decision_record.py              # DecisionRecord dataclass + SHA-256 hash
    ├── watsonx_client.py               # IBM watsonx.ai (Granite) wrapper
    ├── cos_client.py                   # IBM Cloud Object Storage wrapper
    └── dal_engine.py                   # Orchestration layer
```

---

## Documentation

| Doc | Contents |
|---|---|
| [concept.md](docs/concept.md) | Project thesis, core scenario walkthrough, five DAL elements |
| [problem-statement.md](docs/problem-statement.md) | The accountability gap in AI-assisted security workflows |
| [decision-assurance-framework.md](docs/decision-assurance-framework.md) | Formal framework with field-level schema tables |
| [architecture-draft.md](docs/architecture-draft.md) | Component diagram, data flow, technology choices |
| [threat-model.md](docs/threat-model.md) | Trust boundaries, 15 threats with mitigations, hardening checklist |
| [user-stories.md](docs/user-stories.md) | 9 user stories — analyst, manager, and auditor workflows |
| [ibm-bob-usage-plan.md](docs/ibm-bob-usage-plan.md) | How IBM Bob was used throughout this project |
| [judging-criteria-map.md](docs/judging-criteria-map.md) | Every judging criterion mapped to a specific project artefact |

---

## Secondary Milestones (Post-MVP)

1. **Ranked action list with uncertainty scores** — expand AI response to a ranked table of N possible actions, each with individual confidence scores
2. **FastAPI / CLI path** — expose the DAL engine as a REST API for pipeline integration and automated testing
3. **Jupyter notebook walkthrough** — narrative incident walkthrough calling the DAL engine directly, suitable as a submission write-up

---

## Built With

- [IBM watsonx.ai](https://www.ibm.com/products/watsonx-ai) — Granite model for AI recommendation generation
- [IBM Cloud Object Storage](https://www.ibm.com/cloud/object-storage) — Immutable audit record persistence
- [IBM Bob](https://www.ibm.com/) — Used for planning, documentation, and code implementation throughout
- [Streamlit](https://streamlit.io/) — Analyst workbench UI

---

## License

See [LICENSE](LICENSE).
