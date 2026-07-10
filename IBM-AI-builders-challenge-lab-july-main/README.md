# Decision Assurance Layer for AI-Assisted Cybersecurity

IBM AI Builders Challenge July Wildcard project.

## Project Thesis

> **Future cybersecurity is not AI autonomy. Future cybersecurity is accountable AI-assisted command and control.**

## What This Is

The **Decision Assurance Layer (DAL)** is a prototype that sits between AI-generated threat recommendations and human SOC analyst decisions. It enforces a structured judgment checkpoint: the AI analyses the alert, the analyst reviews evidence and AI output side-by-side, makes an explicit approve / reject / override decision with a documented rationale, and an immutable SHA-256-hashed audit record is saved to IBM Cloud Object Storage.

Every `DecisionRecord` captures five elements: **evidence bundle**, **AI recommendation**, **uncertainty score**, **human judgment**, and **audit record**. None are optional.

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd IBM-AI-builders-challenge-lab-july-main

# 2. Install dependencies (Python 3.10+)
pip install -r requirements.txt

# 3. Configure credentials (optional — demo mode works without them)
cp .env.example .env
# Edit .env and fill in your IBM credentials

# 4. Run the app
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

**No IBM credentials?** The app runs in Demo Mode automatically — mock AI responses and local file storage replace the live IBM services. All functionality works end-to-end.

---

## IBM Credential Setup

Copy `.env.example` to `.env` and fill in the following values. **Never commit `.env` to version control.**

| Variable | Where to find it |
|---|---|
| `WATSONX_API_KEY` | IBM Cloud → IAM → API Keys |
| `WATSONX_PROJECT_ID` | watsonx.ai → Your project → Manage → General |
| `WATSONX_URL` | `https://us-south.ml.cloud.ibm.com` (Dallas) |
| `COS_API_KEY` | IBM Cloud → Cloud Object Storage → Service credentials |
| `COS_INSTANCE_CRN` | IBM Cloud → Cloud Object Storage → Resource Instance ID |
| `COS_ENDPOINT` | IBM Cloud → Cloud Object Storage → Endpoints |
| `COS_BUCKET_NAME` | Name of a bucket you have created in your COS instance |

**COS prerequisite:** The bucket named in `COS_BUCKET_NAME` must already exist before running the app. Create it in the IBM Cloud COS dashboard.

---

## Architecture Overview

```
Scenario Fixtures (data/scenarios/*.json)
    |
    v
dal_engine.py  <-->  watsonx_client.py  -->  IBM watsonx.ai (Granite)
    |                                         [fallback: mock response]
    v
Streamlit UI (app.py)
    |
    v
cos_client.py  -->  IBM Cloud Object Storage  decisions/{id}.json
                    [fallback: data/decisions/]
```

The five DAL elements flow through every layer:

1. **Evidence Bundle** — scenario fixture JSON → displayed in the analyst workbench
2. **AI Recommendation** — Granite model output → recommendation + reasoning card
3. **Uncertainty Score** — `ai_confidence` float → colour-coded badge (green / amber / red)
4. **Human Judgment** — analyst action form → approve / reject / override + rationale
5. **Audit Record** — `DecisionRecord` with SHA-256 hash → persisted to IBM COS

---

## File Structure

```
.
├── app.py                         # Streamlit entry point
├── requirements.txt               # Python dependencies
├── .env.example                   # Credential template (copy to .env)
├── mvp-plan.md                    # Implementation plan with sub-task tracking
├── docs/
│   ├── concept.md                 # What the DAL is and why
│   ├── problem-statement.md       # The specific problem being solved
│   ├── decision-assurance-framework.md  # The five-element framework
│   ├── architecture-draft.md      # Component diagram and data flow
│   ├── threat-model.md            # Trust boundaries and mitigations
│   ├── user-stories.md            # SOC analyst and auditor stories
│   ├── ibm-bob-usage-plan.md      # How IBM Bob was used in this project
│   └── judging-criteria-map.md    # Criteria → artefacts mapping
├── data/
│   ├── scenarios/
│   │   ├── scenario_001.json      # Lateral movement via SMB (HIGH)
│   │   ├── scenario_002.json      # Ransomware precursor (CRITICAL)
│   │   └── scenario_003.json      # Credential stuffing (MEDIUM)
│   └── decisions/                 # Local fallback decision record storage
└── src/
    ├── __init__.py
    ├── scenario_loader.py         # Loads scenario fixtures
    ├── decision_record.py         # DecisionRecord dataclass + SHA-256 hash
    ├── watsonx_client.py          # IBM watsonx.ai (Granite) wrapper
    ├── cos_client.py              # IBM Cloud Object Storage wrapper
    └── dal_engine.py              # Orchestration layer
```

---

## Documentation

| Document | Description |
|---|---|
| [`docs/concept.md`](docs/concept.md) | Project concept and the five DAL elements explained |
| [`docs/problem-statement.md`](docs/problem-statement.md) | The accountability gap in AI-assisted security workflows |
| [`docs/decision-assurance-framework.md`](docs/decision-assurance-framework.md) | Formal framework with field-level schema |
| [`docs/architecture-draft.md`](docs/architecture-draft.md) | Component diagram and end-to-end data flow |
| [`docs/threat-model.md`](docs/threat-model.md) | Trust boundaries and production hardening checklist |
| [`docs/user-stories.md`](docs/user-stories.md) | User stories covering analyst and auditor workflows |
| [`docs/ibm-bob-usage-plan.md`](docs/ibm-bob-usage-plan.md) | How IBM Bob was used throughout this project |
| [`docs/judging-criteria-map.md`](docs/judging-criteria-map.md) | Judging criteria → project artefacts mapping |

---

## Secondary Milestones (Post-MVP)

1. **Ranked action list with uncertainty scores** — expand AI response to a ranked table of N actions with individual confidence scores
2. **FastAPI / CLI path** — expose the DAL engine as a REST API for pipeline integration and automated testing
3. **Jupyter notebook walkthrough** — narrative incident walkthrough calling the DAL engine directly, suitable as a submission write-up

---

## License

See [LICENSE](LICENSE).
