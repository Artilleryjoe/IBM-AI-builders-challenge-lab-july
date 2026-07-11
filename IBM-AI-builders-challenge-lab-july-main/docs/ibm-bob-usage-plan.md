# IBM Bob Usage Plan

## Overview

This document records how IBM Bob (the AI coding and planning assistant built on IBM watsonx) was used throughout the IBM AI Builders Challenge July Wildcard project. It serves as evidence of the "IBM Bob usage" requirement and as a transparent log of AI-assisted development decisions.

---

## Roles Bob Played in This Project

### 1. Initial Project Assessment

Bob was used to perform the first read of the repository after it was created. With only a `README.md` and empty placeholder doc files, Bob assessed the project state, identified what was present versus missing, and provided a structured gap analysis. This gave the project a clear starting point rather than a blank page.

**Outcome:** Clear identification of 8 empty documentation files and the need for a concrete implementation plan before writing any code.

---

### 2. MVP Architecture Planning

Bob guided the project through a structured planning workflow:
- Asked targeted clarifying questions to nail down the MVP scope (UI type, AI backend, persistence, data source)
- Proposed a 7-sub-task implementation plan with explicit intent, expected outcomes, and ordered todo lists for each sub-task
- Produced `mvp-plan.md` as a written, versioned plan document

The plan was reviewed and a user-requested change was made (sub-task ordering) before implementation began. Bob re-ordered the sub-tasks and updated the rationale for the change in the plan document.

**Outcome:** `mvp-plan.md` — a complete, structured implementation plan that serves as the project's source of truth.

---

### 3. Data Model and Fixture Design (Sub-Task 1)

Bob implemented all files in Sub-Task 1:
- Designed and wrote three realistic threat scenario JSON fixtures (`scenario_001`, `scenario_002`, `scenario_003`) covering lateral movement, ransomware precursor, and credential stuffing scenarios with MITRE ATT&CK mappings and realistic timestamped evidence entries
- Designed and implemented the `DecisionRecord` dataclass with SHAKE-256 (post-quantum-resilient) tamper-evidence hashing, factory method, and JSON serialisation
- Implemented `scenario_loader.py` with module-level caching and graceful error handling
- Ran a validation smoke-test and identified and fixed a cross-platform encoding issue with em-dash characters in the fixture titles

**Outcome:** `src/decision_record.py`, `src/scenario_loader.py`, `data/scenarios/scenario_*.json` — all validated.

---

### 4. Documentation Writing (Sub-Task 2)

Bob wrote all 8 documentation files that were previously empty:
- `docs/concept.md` — project thesis, core scenario walkthrough, five DAL elements table
- `docs/problem-statement.md` — structural problem analysis, target users, scope boundaries
- `docs/decision-assurance-framework.md` — formal framework document with field-level schema tables and a consistency matrix
- `docs/user-stories.md` — 9 user stories covering all MVP and post-MVP workflows
- `docs/architecture-draft.md` — ASCII component diagram, end-to-end data flow walkthrough, fallback architecture table, technology choices
- `docs/threat-model.md` — 5 trust boundaries, 15 specific threats with mitigations, production hardening checklist
- `docs/ibm-bob-usage-plan.md` — this document
- `docs/judging-criteria-map.md` — maps each IBM challenge judging criterion to project artefacts

**Outcome:** All 8 `docs/` files populated with substantive content grounded in the data model from Sub-Task 1.

---

### 5. Code Implementation (Sub-Tasks 3-7)

Bob implemented the remaining application code sub-tasks:
- `src/watsonx_client.py` — IBM watsonx.ai SDK wrapper with Granite model integration, structured prompt engineering, response parsing, and mock fallback
- `src/cos_client.py` — IBM Cloud Object Storage wrapper with save/list/fallback
- `src/dal_engine.py` — orchestration layer tying all modules together
- `app.py` — complete Streamlit analyst workbench UI
- Integration, wiring validation, and README update

---

## What Bob Did NOT Do

- Bob did not choose the project concept — the thesis ("accountable AI-assisted command and control") was defined by the project owner before Bob was involved
- Bob did not make unilateral architecture decisions — every significant choice (Streamlit vs React, watsonx.ai vs OpenAI, COS vs SQLite) was presented as options and decided by the project owner
- Bob's code was reviewed before being accepted as the working baseline

---

## Conversation Pattern Used

The project used a plan-then-implement pattern:
1. Bob assessed the existing repo and proposed a plan
2. The project owner reviewed, approved (with one requested change), and confirmed before implementation began
3. Bob implemented one sub-task at a time, reported what was done, and waited for the "proceed" signal before moving to the next sub-task
4. The plan document (`mvp-plan.md`) was updated with completion status after each sub-task

This pattern preserved human control over the project direction at every step — which is appropriate for a project whose core thesis is about human oversight of AI systems.

---

## Reflection

Using Bob to build a project about AI accountability creates an interesting recursive quality. The project argues that AI-generated outputs should be accompanied by evidence, reasoning, and human judgment. The plan-then-implement workflow used here is a practical demonstration of that principle: Bob's outputs (the plan, the code, the documentation) were reviewed by a human before being committed as project artefacts. Bob's role was to accelerate, not to decide.
