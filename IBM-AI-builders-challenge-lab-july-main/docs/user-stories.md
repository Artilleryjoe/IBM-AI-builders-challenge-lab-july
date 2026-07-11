# User Stories

## Roles

| Role | Description |
|---|---|
| **SOC Analyst** | A security analyst working in a Security Operations Centre who reviews and acts on threat alerts, with AI assistance |
| **SOC Manager / IR Lead** | A senior analyst or incident response team lead who reviews decisions made during an incident for quality assurance and post-incident review |
| **Auditor / Compliance Officer** | A person responsible for demonstrating that AI-assisted decisions were subject to human oversight and are traceable |

---

## Core Workflow Stories (MVP)

### US-01 — Analyst Reviews an AI-Generated Threat Recommendation

**As a** SOC analyst,
**I want to** see an AI-generated recommendation for a threat alert alongside the raw evidence the AI used,
**so that** I can make an informed decision rather than blindly accepting or rejecting an opaque verdict.

**Acceptance criteria:**
- The analyst can select any available threat scenario from a dropdown
- The analyst can trigger an AI analysis of the selected scenario
- The UI displays: alert title, severity, alert type, MITRE tactic, raw evidence entries, AI recommendation, AI reasoning, and AI suggested actions
- The UI displays the AI confidence score as a colour-coded badge (green / amber / red)
- All evidence and AI output is visible before the analyst is asked to act

---

### US-02 — Analyst Approves an AI Recommendation

**As a** SOC analyst,
**I want to** formally approve an AI recommendation with a documented rationale,
**so that** my agreement is captured as an explicit, reviewable decision rather than a passive click.

**Acceptance criteria:**
- The analyst can select "Approve" as their action
- The analyst must enter a non-empty rationale before submitting
- On submission, a `DecisionRecord` is created with `analyst_action = "approve"` and the entered rationale
- The record is assigned a unique `record_id` and a UTC `timestamp`
- The record is hashed and saved to IBM Cloud Object Storage (or local fallback)
- The UI displays the saved `record_id` and `record_hash` in a confirmation banner

---

### US-03 — Analyst Overrides an AI Recommendation

**As a** SOC analyst,
**I want to** override an AI recommendation and document the alternative action I am taking,
**so that** my independent judgment is captured and the override is not silently lost.

**Acceptance criteria:**
- The analyst can select "Override" as their action
- When Override is selected, an additional "Override Description" field appears and is required
- The analyst must enter both a rationale and an override description before submitting
- On submission, a `DecisionRecord` is created with `analyst_action = "override"`, `analyst_rationale`, and `override_description` populated
- The record is hashed and saved identically to an approval
- The UI confirmation banner clearly indicates the decision was an override

---

### US-04 — Analyst Rejects an AI Recommendation

**As a** SOC analyst,
**I want to** reject an AI recommendation when I believe the alert is a false positive,
**so that** my disagreement is formally recorded rather than simply taking no action.

**Acceptance criteria:**
- The analyst can select "Reject" as their action
- The analyst must enter a rationale explaining why they are rejecting the recommendation
- On submission, a `DecisionRecord` is created with `analyst_action = "reject"` and the rationale
- The record is saved and hashed identically to other action types

---

### US-05 — Auditor Reviews the Decision Log

**As a** compliance officer,
**I want to** view a log of all analyst decisions made through the system, including the AI recommendation and the analyst's rationale,
**so that** I can demonstrate to regulators that AI-assisted decisions were subject to documented human oversight.

**Acceptance criteria:**
- An Audit Log view is available in the UI
- The log shows: `record_id`, `scenario_title`, `analyst_action`, `timestamp`, and `record_hash` for each saved decision
- All records are displayed regardless of action type (approve / reject / override)
- The `record_hash` is visible and can be used to verify record integrity externally

---

### US-06 — SOC Manager Reviews a Specific Past Decision

**As a** SOC manager conducting a post-incident review,
**I want to** retrieve the full `DecisionRecord` for a specific alert decision,
**so that** I can understand exactly what the AI recommended, how confident it was, and why the analyst acted as they did.

**Acceptance criteria:**
- Each `DecisionRecord` contains all five DAL elements in a single, self-contained JSON document
- The record includes the AI recommendation, confidence score, reasoning, analyst action, rationale, and a tamper-evident hash
- The record is persisted to IBM Cloud Object Storage and can be retrieved by `record_id`
- The SHAKE-256 hash of the record can be independently verified against the stored content

---

## Secondary Milestone Stories (Post-MVP)

### US-07 — Analyst Reviews Ranked Action Options

**As a** SOC analyst,
**I want to** see a ranked list of possible actions the AI considered — not just its top recommendation — with individual confidence scores,
**so that** I can make a more nuanced judgment when the top recommendation is uncertain.

*Target: Secondary Milestone 1 — Ranked action list with uncertainty scores.*

---

### US-08 — Integration Test via CLI / API

**As a** security architect evaluating the DAL,
**I want to** drive the full workflow via a REST API or CLI without a UI,
**so that** I can integrate the DAL into an existing pipeline or write automated integration tests.

*Target: Secondary Milestone 2 — CLI / API path.*

---

### US-09 — Walkthrough of a Simulated Incident

**As a** challenge judge or technical evaluator,
**I want to** follow a narrative Jupyter notebook that walks through a complete simulated incident,
**so that** I can understand the DAL pattern end-to-end without running the application.

*Target: Secondary Milestone 3 — Jupyter notebook walkthrough.*
