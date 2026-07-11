# Architecture Draft

## Overview

The MVP is a single-tier Python application with three external dependencies: IBM watsonx.ai for AI generation, IBM Cloud Object Storage for audit record persistence, and the local filesystem as a fallback for both. There is no separate database, no message queue, and no background worker — the system is intentionally minimal to demonstrate the DAL pattern without infrastructure complexity.

---

## Component Diagram

```
+--------------------------------------------------------------------+
|                       app.py (Streamlit UI)                        |
|                                                                    |
|  +---------------+  +------------------------+  +---------------+ |
|  | Scenario      |  | Analyst Workbench      |  | Audit Log     | |
|  | Selector      |  | (Evidence + AI Card)   |  | Tab           | |
|  +-------+-------+  +-----------+------------+  +-------+-------+ |
+----------|-----------------------|----------------------|-----------+
           |                       |                      |
           v                       v                      v
+--------------------------------------------------------------------------+
|                         src/dal_engine.py                                |
|                                                                          |
|   get_recommendation(scenario_id)         get_audit_log()               |
|   submit_decision(...)                                                   |
+----------+--------------------------------------------------+------------+
           |                                                  |
           v                                                  v
+---------------------+                      +-------------------------------+
| src/scenario_loader |                      | src/cos_client.py             |
| .py                 |                      |                               |
|                     |                      | save_decision_record()        |
| list_scenarios()    |                      | list_decision_records()       |
| get_scenario(id)    |                      +---------------+---------------+
+----------+----------+                                      |
           |                                                 v
           v                                +--------------------------------+
+---------------------+                     | IBM Cloud Object Storage       |
| data/scenarios/     |                     | decisions/{record_id}.json     |
| *.json              |                     |                                |
| (fixture files)     |                     | [Fallback: data/decisions/]    |
+---------------------+                     +--------------------------------+
           |
           | also feeds into
           v
+--------------------------------------+
| src/watsonx_client.py                |
|                                      |
| generate_recommendation(scenario)    |
|                                      |
| -> IBM watsonx.ai (Granite model)    |
| [Fallback: mock response dict]       |
+--------------------------------------+
           |
           v
+---------------------+
| src/decision_record |
| .py                 |
|                     |
| DecisionRecord      |
| .create()           |
| .compute_hash()     |
| .to_json()          |
+---------------------+
```

---

## Data Flow: End-to-End Walkthrough

### Step 1 — Scenario Selection
The analyst opens the Streamlit app. The sidebar populates a dropdown with scenario titles loaded by `scenario_loader.list_scenarios()` from the `data/scenarios/*.json` fixture files. No network calls are made at this point.

### Step 2 — AI Recommendation Request
The analyst clicks **Get AI Recommendation**. `dal_engine.get_recommendation(scenario_id)` is called. It:
1. Loads the scenario dict via `scenario_loader.get_scenario()`
2. Constructs a structured prompt containing the scenario title, severity, MITRE tactic, and raw evidence entries
3. Calls `watsonx_client.generate_recommendation(scenario)`, which sends the prompt to IBM watsonx.ai (Granite model) via the `ibm-watsonx-ai` Python SDK
4. Parses the model's JSON response into a dict with keys: `recommendation`, `confidence_score`, `reasoning`, `suggested_actions`
5. Returns the combined scenario + AI response dict to the UI via `st.session_state`

If the watsonx.ai API is unavailable or credentials are not set, `watsonx_client` returns a hardcoded mock response automatically.

### Step 3 — Analyst Review
The UI renders the evidence panel (left column) and the AI recommendation card (right column). The confidence score is displayed as a colour-coded badge. The analyst reads both panels before acting.

### Step 4 — Analyst Decision
The analyst fills in the action form:
- Selects an action: Approve / Reject / Override
- Types a rationale (required)
- If Override: types an override description (required)

Clicking **Submit Decision** calls `dal_engine.submit_decision(scenario_id, analyst_action, rationale, override_text)`.

### Step 5 — Record Creation and Persistence
`dal_engine.submit_decision` assembles a `DecisionRecord` via `DecisionRecord.create()`:
- Stamps `record_id` (UUID4) and `timestamp` (UTC ISO-8601)
- Computes `record_hash` (SHAKE-256 over all fields except the hash itself, keys sorted — PQC-resilient)

The completed record is passed to `cos_client.save_decision_record(record)`, which uploads it to IBM COS under `decisions/{record_id}.json`. If COS is unavailable, the local fallback saves it to `data/decisions/{record_id}.json`.

### Step 6 — Confirmation and Audit Log
The UI displays a success banner with the `record_id` and `record_hash`. The Audit Log tab calls `dal_engine.get_audit_log()` -> `cos_client.list_decision_records()` to render all saved decisions in a table.

---

## Fallback Architecture

Both external IBM services have explicit fallbacks to ensure the demo runs without credentials:

| Service | Primary | Fallback | Trigger |
|---|---|---|---|
| IBM watsonx.ai | `ibm-watsonx-ai` SDK -> Granite model | Hardcoded mock response dict | Missing env vars or API error |
| IBM Cloud Object Storage | `ibm-cos-sdk-python` -> COS bucket | Local filesystem `data/decisions/` | Missing env vars or SDK init failure |

The fallback path is used automatically. The UI displays a `Demo Mode` banner when running without IBM credentials.

---

## File Structure

```
IBM-AI-builders-challenge-lab-july-main/
|-- app.py                             # Streamlit entry point
|-- requirements.txt                   # Python dependencies
|-- .env.example                       # Credential template
|-- mvp-plan.md                        # Project plan
|-- docs/                              # All documentation
|-- data/
|   |-- scenarios/                     # Input: threat scenario fixtures
|   |   |-- scenario_001.json
|   |   |-- scenario_002.json
|   |   +-- scenario_003.json
|   +-- decisions/                     # Fallback: local decision record storage
+-- src/
    |-- __init__.py
    |-- scenario_loader.py             # Fixture loading
    |-- decision_record.py             # DecisionRecord data model
    |-- watsonx_client.py              # IBM watsonx.ai wrapper
    |-- cos_client.py                  # IBM COS wrapper
    +-- dal_engine.py                  # Orchestration layer
```

---

## Technology Choices

| Component | Technology | Rationale |
|---|---|---|
| UI | Streamlit | No frontend build step; Python-only; rapid prototyping |
| AI | IBM watsonx.ai (Granite) | IBM-native; strong instruct model for structured output |
| Persistence | IBM Cloud Object Storage | IBM-native; immutable object storage; aligns with audit requirements |
| Data model | Python `dataclasses` | Zero dependencies; serializes cleanly to JSON |
| Hashing | `hashlib.sha256` (stdlib) | No dependencies; industry-standard tamper-evidence pattern |
| Env management | `python-dotenv` | Standard practice for credential handling |

---

## Constraints and Assumptions

- **Single analyst, single session** — no multi-user state, no authentication in the MVP
- **Fixtures are static** — no live threat feed; scenario data does not change at runtime
- **No streaming** — the watsonx.ai call is synchronous; a spinner covers the latency
- **COS bucket pre-created** — the bucket must exist before the app runs; setup documented in README
- **Python 3.10+** — uses `dataclasses`, `pathlib`, `__future__ annotations`
