# MVP Plan — Decision Assurance Layer for AI-Assisted Cybersecurity

## Top-Level Overview

**Goal:** Build a small, end-to-end prototype that demonstrates a SOC analyst receiving an
AI-generated threat alert recommendation, reviewing supporting evidence, approving or
overriding the decision, and saving an immutable auditable record — all within a single
Streamlit UI backed by IBM watsonx.ai (Granite) and IBM Cloud Object Storage (COS).

**Scope:**
- Streamlit UI (single Python app, no separate frontend build)
- IBM watsonx.ai via the `ibm-watsonx-ai` Python SDK for AI recommendation generation
- IBM Cloud Object Storage (COS) via `ibm-cos-sdk` for decision record persistence
- Hardcoded JSON scenario fixtures as the simulated threat alert data source
- No authentication layer, no multi-user session management — single-analyst demo

**Non-goals for MVP:**
- Live threat intelligence feed integration
- Multi-user / role-based access control
- Production deployment / containerization
- Full ranked action list with uncertainty scores (secondary milestone, post-MVP)
- CLI path (secondary milestone, post-MVP)
- Jupyter notebook walkthrough (secondary milestone, post-MVP)

**IBM Challenge alignment:**
- Uses IBM watsonx.ai (Granite model) for AI generation
- Uses IBM Cloud Object Storage for persistence
- Directly demonstrates the challenge thesis: accountable AI-assisted command and control

---

## Recommended File Structure

```
IBM-AI-builders-challenge-lab-july-main/
├── README.md
├── mvp-plan.md                        ← this file
├── requirements.txt                   ← Python dependencies
├── .env.example                       ← env var template (no secrets committed)
├── docs/
│   ├── concept.md
│   ├── problem-statement.md
│   ├── architecture-draft.md
│   ├── decision-assurance-framework.md
│   ├── threat-model.md
│   ├── user-stories.md
│   ├── ibm-bob-usage-plan.md
│   └── judging-criteria-map.md
├── data/
│   └── scenarios/
│       ├── scenario_001.json          ← hardcoded threat alert fixture
│       ├── scenario_002.json
│       └── scenario_003.json
├── src/
│   ├── watsonx_client.py              ← watsonx.ai SDK wrapper
│   ├── cos_client.py                  ← IBM COS SDK wrapper
│   ├── decision_record.py             ← Decision record data model
│   ├── scenario_loader.py             ← loads fixtures from data/scenarios/
│   └── dal_engine.py                  ← orchestrates: load scenario → call AI → return recommendation
└── app.py                             ← Streamlit entry point
```

---

## Sub-Tasks

---

### Sub-Task 1 — Define the Data Models and Scenario Fixtures

**Status:** `[x] done`

**Intent:**
Establish the data contracts the entire system is built on before writing any logic code.
A scenario fixture is the input; a decision record is the output. Both must be defined first.

**Expected Outcomes:**
- `data/scenarios/scenario_001.json`, `scenario_002.json`, `scenario_003.json` exist with
  realistic, varied threat alert content (different alert types, severities, evidence fields)
- `src/decision_record.py` defines the `DecisionRecord` dataclass/schema with all required
  fields: scenario_id, alert summary, AI recommendation, confidence score, analyst action
  (approve/reject/override), analyst rationale, override text (if applicable), timestamp,
  analyst ID (stubbed), and record hash for tamper-evidence
- `src/scenario_loader.py` can load a scenario fixture by ID and return a typed object

**Todo List:**
1. Define the scenario fixture JSON schema — fields: `id`, `title`, `severity`, `source_ip`,
   `destination_ip`, `alert_type`, `raw_evidence` (list of evidence strings), `timestamp`,
   `mitre_tactic` (optional)
2. Write `data/scenarios/scenario_001.json` — a lateral movement alert with network evidence
3. Write `data/scenarios/scenario_002.json` — a ransomware precursor / suspicious file
   execution alert
4. Write `data/scenarios/scenario_003.json` — a credential stuffing / authentication anomaly
   alert
5. Define the `DecisionRecord` data model in `src/decision_record.py` — include a method to
   serialize to JSON and compute a SHA-256 hash of the record content for tamper-evidence
6. Write `src/scenario_loader.py` — loads all `.json` files from `data/scenarios/` and
   returns a list of scenario objects; can also fetch a single scenario by ID

**Relevant Context:**
- MITRE ATT&CK tactic names add realism to the fixtures without requiring a live API
- The `DecisionRecord` hash field is important for the "audit" story — it shows the record
  cannot be silently altered after saving
- Keep fixtures small (5–8 evidence strings max) so the LLM prompt stays concise

---

### Sub-Task 2 — Write the Core Documentation

**Status:** `[x] done`

**Intent:**
Fill the empty placeholder docs so the project has a written foundation that judges can
read and that grounds every subsequent implementation decision. This is documentation, not
code — but it is a deliverable in its own right. The data models from Sub-Task 1 provide
the concrete field names and five DAL elements that the docs should reference.

**Expected Outcomes:**
- `docs/concept.md` explains what the Decision Assurance Layer is, with a concrete scenario
- `docs/problem-statement.md` articulates the gap being filled, with specifics
- `docs/decision-assurance-framework.md` defines the five elements (evidence, recommendation,
  uncertainty score, human judgment, audit record) and their relationships
- `docs/user-stories.md` has at least 3 user stories covering the SOC analyst workflow
- `docs/architecture-draft.md` describes the MVP component diagram in prose
- `docs/threat-model.md` identifies the key trust boundaries and abuse cases for the DAL
- `docs/ibm-bob-usage-plan.md` documents how Bob (this tool) was used in the challenge
- `docs/judging-criteria-map.md` maps each judging criterion to a concrete project artifact

**Todo List:**
1. Write `docs/concept.md` — define the Decision Assurance Layer, explain the core scenario
   (SOC analyst + AI recommendation + human override + audit record), and state the thesis
2. Write `docs/problem-statement.md` — name the specific problem (AI in security ops without
   accountability), reference real-world context, define the gap
3. Write `docs/decision-assurance-framework.md` — define the five DAL elements as a formal
   mini-framework, explain each element's purpose and data fields (use field names from
   `DecisionRecord` defined in Sub-Task 1)
4. Write `docs/user-stories.md` — at least 3 stories: analyst reviews alert, analyst overrides
   AI recommendation, auditor reviews decision log
5. Write `docs/architecture-draft.md` — describe the MVP components and data flow in prose:
   fixture → DAL engine → watsonx.ai → Streamlit UI → COS
6. Write `docs/threat-model.md` — identify trust boundaries: AI output trustworthiness,
   record tampering, analyst coercion by AI framing
7. Write `docs/ibm-bob-usage-plan.md` — document how Bob was used: planning, doc generation,
   code scaffolding, review
8. Write `docs/judging-criteria-map.md` — map each IBM challenge judging criterion to project
   artifacts, explain how this project satisfies each one

**Relevant Context:**
- All files exist as empty placeholders in `docs/`
- The README thesis statement is the seed: "accountable AI-assisted command and control"
- The five DAL elements (evidence, recommendation, uncertainty, human judgment, audit record)
  should be consistent across all docs and match the `DecisionRecord` fields from Sub-Task 1

---

### Sub-Task 3 — IBM watsonx.ai Integration

**Status:** `[x] done`

**Intent:**
Wire up the IBM watsonx.ai SDK so the DAL engine can send a threat scenario to a Granite
model and receive a structured recommendation with a confidence score.

**Expected Outcomes:**
- `src/watsonx_client.py` wraps the `ibm-watsonx-ai` SDK, reads credentials from environment
  variables, and exposes a single `generate_recommendation(scenario) -> dict` function
- The function returns: `recommendation` (string), `confidence_score` (float 0–1),
  `reasoning` (string), `suggested_actions` (list of strings)
- The prompt is a well-engineered system prompt that instructs Granite to act as a
  cybersecurity analyst assistant and return structured output
- `requirements.txt` includes `ibm-watsonx-ai` and all other dependencies
- `.env.example` documents the required environment variables

**Todo List:**
1. Add `ibm-watsonx-ai` to `requirements.txt` along with `streamlit`, `ibm-cos-sdk-python`,
   `python-dotenv`, and any other dependencies
2. Create `.env.example` with placeholders for: `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`,
   `WATSONX_URL`, `COS_API_KEY`, `COS_INSTANCE_CRN`, `COS_ENDPOINT`, `COS_BUCKET_NAME`
3. Write `src/watsonx_client.py` — initialize the `APIClient` and `ModelInference` from
   `ibm_watsonx_ai`; use `ibm/granite-13b-instruct-v2` or the best available Granite model
4. Write the system prompt for Granite — instruct it to analyze the threat scenario, state
   its recommendation (investigate / escalate / dismiss), provide a confidence score (0–1),
   explain its reasoning, and list 2–3 suggested actions
5. Write a response parser that extracts the structured fields from the model's text output
   (use a simple delimited format or ask Granite to respond in JSON)
6. Add a `fallback_mock_response()` function that returns a realistic hardcoded response when
   the API is unavailable — ensures the demo works offline

**Relevant Context:**
- `WATSONX_URL` is typically `https://us-south.ml.cloud.ibm.com` for the Dallas region
- Granite instruct models respond well to structured prompts asking for JSON output
- The confidence score is a key DAL element — it communicates AI uncertainty to the analyst

---

### Sub-Task 4 — IBM Cloud Object Storage Integration

**Status:** `[x] done`

**Intent:**
Wire up IBM COS so that every finalized decision record is persisted to the cloud with a
unique key, creating an immutable, queryable audit trail.

**Expected Outcomes:**
- `src/cos_client.py` wraps the `ibm-cos-sdk-python` SDK, reads credentials from environment
  variables, and exposes two functions: `save_decision_record(record)` and
  `list_decision_records() -> list`
- Each record is stored as a JSON object with key `decisions/{record_id}.json`
- `list_decision_records()` returns a list of all stored decision metadata for the audit log view
- A `fallback_local_save(record)` function saves to `data/decisions/` on disk when COS is
  unavailable — ensures demo works without cloud credentials

**Todo List:**
1. Write `src/cos_client.py` — initialize `ibm_boto3` client using `COS_API_KEY`,
   `COS_INSTANCE_CRN`, and `COS_ENDPOINT` from environment variables
2. Implement `save_decision_record(record: DecisionRecord) -> str` — serialize the record to
   JSON, upload to `COS_BUCKET_NAME` under key `decisions/{record.id}.json`, return the key
3. Implement `list_decision_records() -> list[dict]` — list objects under the `decisions/`
   prefix, fetch each, and return as a list of dicts for display in the UI
4. Implement `fallback_local_save(record)` — save to `data/decisions/{record_id}.json` on
   disk; create the directory if it does not exist
5. Add graceful fallback: if COS client initialization fails, log a warning and route all
   save/list calls to the local fallback automatically

**Relevant Context:**
- `ibm-cos-sdk-python` uses the `ibm_boto3` interface, which mirrors the `boto3` AWS SDK API
- The bucket must exist before writing — document this as a setup prerequisite in the README
- The `decisions/` prefix creates a logical namespace within the bucket for easy listing

---

### Sub-Task 5 — DAL Engine (Orchestration Layer)

**Status:** `[x] done`

**Intent:**
Build the thin orchestration layer that ties scenario loading, AI generation, and record
creation together into a single clean API that the Streamlit UI calls.

**Expected Outcomes:**
- `src/dal_engine.py` exposes two functions: `get_recommendation(scenario_id) -> dict` and
  `submit_decision(scenario_id, analyst_action, rationale, override_text) -> DecisionRecord`
- `get_recommendation` loads the scenario fixture and calls `watsonx_client.generate_recommendation`
- `submit_decision` assembles a `DecisionRecord`, computes its hash, saves it via
  `cos_client.save_decision_record`, and returns the saved record
- The engine has no UI logic — it is pure data transformation and coordination

**Todo List:**
1. Write `src/dal_engine.py` — import `scenario_loader`, `watsonx_client`, `cos_client`,
   `decision_record`
2. Implement `get_recommendation(scenario_id: str) -> dict` — load scenario, build prompt
   context, call watsonx, return scenario + AI response as a combined dict for the UI
3. Implement `submit_decision(...)` — build a `DecisionRecord` from the analyst's inputs,
   stamp it with a UTC timestamp and a UUID record ID, compute SHA-256 hash, call
   `cos_client.save_decision_record`, return the completed record
4. Add a `get_audit_log() -> list[dict]` function that calls `cos_client.list_decision_records`
   and returns the list for the audit log view in the UI

**Relevant Context:**
- The UUID for `record.id` should be deterministic if needed for testing — use `uuid4()` for
  the MVP
- The SHA-256 hash input should be the JSON-serialized record without the hash field itself,
  then the hash is added back — a standard pattern for self-referential record integrity

---

### Sub-Task 6 — Streamlit UI

**Status:** `[x] done`

**Intent:**
Build the Streamlit app that a judge can run with `streamlit run app.py` and immediately see
the end-to-end workflow: select a scenario, view AI recommendation, approve/override, save
the record, and view the audit log.

**Expected Outcomes:**
- `app.py` is a complete Streamlit app with three views: Analyst Workbench, Decision
  Confirmation, and Audit Log
- Analyst Workbench: scenario selector, raw evidence panel, AI recommendation card
  (with confidence score badge), and approve/reject/override action form
- Decision Confirmation: summary of the saved record including the record hash
- Audit Log: table of all saved decisions fetched from COS (or local fallback)
- The app loads IBM credentials from `.env` via `python-dotenv`
- The app runs end-to-end without errors using the mock/fallback path

**Todo List:**
1. Write `app.py` — set up `st.set_page_config` with title "Decision Assurance Layer — SOC
   Analyst Workbench" and a wide layout
2. Build the sidebar: scenario selector dropdown populated from `scenario_loader`
3. Build the main panel — two columns: left shows raw scenario evidence, right shows the AI
   recommendation card with confidence score visualized as a progress bar or color-coded badge
4. Build the analyst action form: radio button (Approve / Reject / Override), a rationale
   text area (required), an override description text area (shown only when Override selected),
   and a "Submit Decision" button
5. On submit: call `dal_engine.submit_decision`, show a success banner with the record ID and
   hash, offer a "Generate New Recommendation" button to reset
6. Add a "Audit Log" tab or expander: call `dal_engine.get_audit_log()` and render as a
   `st.dataframe` with columns: record_id, scenario_title, analyst_action, timestamp, hash
7. Add a "Get AI Recommendation" button that calls `dal_engine.get_recommendation` and stores
   the result in `st.session_state` — do not auto-call on page load

**Relevant Context:**
- Use `st.session_state` to hold the current recommendation so it survives widget interactions
- The confidence score badge color should follow a simple rule: green >= 0.75, amber 0.5–0.74,
  red < 0.5 — this visually communicates AI uncertainty at a glance
- The record hash in the confirmation view is the key demo moment for "tamper-evidence audit"

---

### Sub-Task 7 — Integration, Wiring, and README Update

**Status:** `[x] done`

**Intent:**
Ensure all components connect correctly end-to-end, the project can be set up from scratch
in under 10 minutes, and the README accurately reflects the final state of the project.

**Expected Outcomes:**
- Running `pip install -r requirements.txt` followed by `streamlit run app.py` produces a
  working demo (with fallback/mock paths if IBM credentials are not set)
- The README has a Quick Start section, architecture overview, and IBM credential setup guide
- All `src/` modules can be imported without errors
- The three scenario fixtures all load and produce AI recommendations without errors

**Todo List:**
1. Update `README.md` — add Quick Start, Prerequisites, IBM Credential Setup (linking to
   `.env.example`), Architecture Overview (prose), and Secondary Milestones sections
2. Verify all imports across `app.py` and `src/` modules are consistent and correct
3. Manually trace the end-to-end path: load scenario_001 → get recommendation (mock) →
   submit approve decision → verify record saved to local fallback → verify audit log shows
   the record
4. Add a top-level `__init__.py` to `src/` if needed to support clean imports
5. Confirm `.gitignore` excludes `.env`, `data/decisions/`, and any `__pycache__` directories

**Relevant Context:**
- The mock/fallback path must work completely without any IBM credentials — this is essential
  for judges who may not have access to the same IBM Cloud account
- The `.env.example` file is the primary onboarding document for credential setup

---

## Secondary Milestones (Post-MVP)

These items were captured from the original brief but are out of scope for the MVP:

1. **Ranked action list with uncertainty scores** — expand the AI response to return a ranked
   list of N possible actions, each with an individual confidence score, displayed as a
   sortable table in the UI
2. **CLI / API path** — expose the DAL engine as a FastAPI REST API so the workflow can be
   driven programmatically, enabling integration testing and a non-UI demo path
3. **Jupyter notebook walkthrough** — a narrative notebook that walks through a simulated
   incident scenario step by step, calling the DAL engine directly, suitable for a blog post
   or challenge submission write-up
