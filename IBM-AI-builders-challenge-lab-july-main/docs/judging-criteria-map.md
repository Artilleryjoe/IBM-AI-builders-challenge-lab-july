# Judging Criteria Map

## Purpose

This document maps each IBM AI Builders Challenge judging criterion to the specific project artefacts that address it. It is intended to help judges quickly locate evidence for each criterion and to demonstrate that the project was designed with the criteria in mind from the start.

---

## Criteria Map

### 1. Use of IBM Technology

**Criterion:** The project makes meaningful use of IBM AI or cloud technology, not just a superficial integration.

| IBM Technology | How It Is Used | Artefact |
|---|---|---|
| **IBM watsonx.ai (Granite model)** | Generates structured threat recommendations (action, confidence score, reasoning, suggested actions) via the `ibm-watsonx-ai` Python SDK | `src/watsonx_client.py` |
| **IBM Cloud Object Storage** | Persists every `DecisionRecord` as an immutable JSON object under `decisions/{record_id}.json` | `src/cos_client.py` |
| **IBM Bob** | Used throughout the project for planning, documentation, and code implementation | `docs/ibm-bob-usage-plan.md`, `mvp-plan.md` |

**Notes:** watsonx.ai is not used as a cosmetic feature — it is the AI backbone of the system. The confidence score it returns drives the visual uncertainty signal in the UI. The COS integration is not a file dump — it creates the immutable, hashed audit trail that is central to the DAL concept.

---

### 2. Innovation / Originality

**Criterion:** The project introduces a novel idea, approach, or application of AI.

**What is novel:**
- The **Decision Assurance Layer pattern** — a structured checkpoint between AI recommendations and human decisions — is not a standard product category. It is a new architectural pattern for AI-assisted security workflows.
- The **five-element framework** (evidence bundle, AI recommendation, uncertainty score, human judgment, audit record) is a composable schema that could be applied beyond cybersecurity to any domain where AI recommendations require human accountability.
- The **uncertainty score as a first-class UI signal** — colour-coded and mandatory — addresses automation bias in a concrete, actionable way that most AI tooling ignores.
- The **recursive framing** — using an AI tool (IBM Bob) to build a project about AI accountability, using a plan-then-confirm workflow that mirrors the DAL's own human oversight model.

**Artefact:** `docs/concept.md`, `docs/decision-assurance-framework.md`

---

### 3. Technical Implementation

**Criterion:** The project is technically sound, well-structured, and demonstrates real implementation rather than just documentation.

| Component | Technical Detail | Artefact |
|---|---|---|
| Data model | `DecisionRecord` dataclass with SHAKE-256 (PQC-resilient) tamper-evidence hashing; factory method; JSON serialisation | `src/decision_record.py` |
| AI integration | `ibm-watsonx-ai` SDK; structured JSON prompt; response parsing; mock fallback | `src/watsonx_client.py` |
| Persistence | `ibm-cos-sdk-python` (ibm_boto3); object upload/list under `decisions/` prefix; local fallback | `src/cos_client.py` |
| Orchestration | Thin `dal_engine.py` with no UI logic; clean separation of concerns | `src/dal_engine.py` |
| UI | Streamlit app with session state management; colour-coded confidence badge; mandatory rationale | `app.py` |
| Scenario data | 10 realistic JSON fixtures with MITRE ATT&CK mappings and timestamped evidence entries | `data/scenarios/` |
| Fallback resilience | Both IBM services degrade gracefully; demo works end-to-end without credentials | `src/watsonx_client.py`, `src/cos_client.py` |

**Artefact:** All `src/` modules, `app.py`, `data/scenarios/`

---

### 4. Real-World Applicability / Impact

**Criterion:** The project addresses a real problem and could have meaningful real-world impact.

**The problem is real:**
- AI-assisted security tooling is deployed at scale in enterprise SOCs today
- Regulatory frameworks (NIS2, DORA, GDPR Article 22) increasingly require demonstrable human oversight of automated decision systems
- Post-incident reviews regularly fail because AI reasoning and analyst judgment were not captured at decision time

**The pattern is applicable beyond the MVP:**
- The DAL schema is not cybersecurity-specific. It applies to any AI-assisted high-stakes decision (medical triage, fraud review, content moderation)
- The five-element framework could be adopted as a lightweight standard for AI accountability in critical operations

**The MVP is a concrete demonstration:**
- A judge can run `streamlit run app.py`, work through a simulated lateral movement incident, approve or override the AI recommendation, and immediately see the hashed `DecisionRecord` appear in the audit log — all in under 5 minutes

**Artefact:** `docs/problem-statement.md`, `docs/concept.md`, `app.py`

---

### 5. Presentation / Documentation Quality

**Criterion:** The project is well-documented and clearly presented.

| Document | Content |
|---|---|
| `README.md` | Project thesis, quick start, architecture overview, credential setup |
| `docs/concept.md` | What the DAL is, core scenario walkthrough, five elements table |
| `docs/problem-statement.md` | Structural problem analysis, target users, scope |
| `docs/decision-assurance-framework.md` | Formal framework with field-level schema tables and consistency matrix |
| `docs/user-stories.md` | 9 user stories covering all MVP and post-MVP workflows |
| `docs/architecture-draft.md` | ASCII component diagram, data flow walkthrough, technology choices |
| `docs/threat-model.md` | 5 trust boundaries, 15 threats with mitigations, production hardening checklist |
| `docs/ibm-bob-usage-plan.md` | Transparent log of Bob usage with outcomes and reflections |
| `mvp-plan.md` | Structured implementation plan with sub-task status tracking |

---

### 6. Use of IBM Bob

**Criterion:** The project demonstrates meaningful, substantive use of IBM Bob as a development tool.

**How Bob was used:**
1. Repo assessment and gap analysis at project start
2. Structured MVP planning (7 sub-tasks, decisions documented, user confirmed before implementation)
3. Data model and fixture implementation with validation
4. All 8 documentation files written by Bob, grounded in the data model
5. Code implementation for all `src/` modules and `app.py`

**What makes this use substantive:**
- Bob did not just generate boilerplate — it designed the architecture, made technology recommendations with rationale, wrote realistic threat scenario content, and engineered the watsonx.ai prompt
- The human controlled every decision point — Bob presented options, the human chose
- The Bob usage itself mirrors the DAL pattern: AI-assisted with human oversight at every step

**Artefact:** `docs/ibm-bob-usage-plan.md`, `mvp-plan.md`, git commit history

---

## Summary Table

| Criterion | Primary Evidence | Supporting Evidence |
|---|---|---|
| IBM Technology | `src/watsonx_client.py`, `src/cos_client.py` | `requirements.txt`, `docs/architecture-draft.md` |
| Innovation | `docs/concept.md`, `docs/decision-assurance-framework.md` | `docs/problem-statement.md` |
| Technical Implementation | `src/`, `app.py`, `data/scenarios/` | `src/decision_record.py` (hash), `mvp-plan.md` |
| Real-World Applicability | `docs/problem-statement.md` | `docs/user-stories.md`, `docs/threat-model.md` |
| Documentation Quality | All `docs/` files | `README.md`, `mvp-plan.md` |
| IBM Bob Usage | `docs/ibm-bob-usage-plan.md` | `mvp-plan.md` |
