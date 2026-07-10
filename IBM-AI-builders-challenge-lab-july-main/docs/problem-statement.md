# Problem Statement

## The Gap This Project Fills

AI-assisted cybersecurity tooling is advancing faster than the governance frameworks needed to use it safely. This project addresses a specific, concrete gap: **the absence of a structured accountability layer between AI-generated threat recommendations and human operator decisions.**

---

## Background

Security Operations Centres now routinely use AI and ML-assisted tools for:
- Alert triage and prioritisation (reducing alert fatigue)
- Threat hunting and anomaly detection
- Incident response recommendation engines
- Automated playbook execution

These tools are effective at processing high volumes of telemetry. They surface patterns that human analysts would miss or reach too slowly. The pressure to automate further — to let AI not just recommend but *act* — is significant. Dwell time reduction is a key SOC metric, and AI can shrink it.

**But this creates a structural problem.**

---

## The Structural Problem

### 1. Evidence is not preserved at the moment of decision

When an AI tool recommends "escalate this alert," the evidence the model used, the weights it applied, and the alternatives it considered are typically not captured in a structured, reviewable form. The analyst receives a verdict, not a reasoning trail. When post-incident reviews ask "why did we respond the way we did?", the answer is often: *we don't know — the AI said so.*

### 2. Human judgment is not formally captured

SOC workflows treat analyst approval as a click, not a decision. There is no structured moment where the analyst documents:
- Why they agreed with (or overrode) the AI
- What their independent assessment of the evidence was
- What they decided to do differently and why

This means the "human in the loop" is largely theatrical — present in name, absent in practice.

### 3. Uncertainty is hidden

AI systems frequently express false confidence. A model that is 51% confident and a model that is 99% confident may produce identically-worded recommendations. Analysts have no signal to indicate when they should scrutinise a recommendation more carefully versus when they can rely on it more heavily. This erodes calibrated trust.

### 4. Audit trails are incomplete or absent

Regulatory frameworks (GDPR, NIS2, DORA in financial services, HIPAA in healthcare) increasingly require organisations to demonstrate that automated decision systems were subject to human oversight. An AI-assisted security decision that cannot be reconstructed, explained, or attributed to a specific human judgment is a compliance liability.

### 5. Override decisions are lost

When an analyst *overrides* an AI recommendation — a valuable signal that the model is wrong or the context has changed — that override is rarely recorded in a structured form. It disappears. The AI system never learns from it. The organisation never benefits from it. It cannot be reviewed.

---

## The Gap

There is no standard, lightweight, open pattern for inserting a **structured human judgment checkpoint** into an AI-assisted security workflow that:

- Captures the evidence bundle at the moment of decision
- Records the AI recommendation and its confidence score
- Requires and preserves the analyst's explicit reasoning
- Produces an immutable, verifiable audit record
- Works with modern AI tooling (LLMs, cloud-native infrastructure)

Proprietary SIEM and SOAR vendors have partial solutions, but they are:
- Expensive and locked into specific platforms
- Not designed around the AI recommendation + human judgment + audit record pattern
- Not focused on uncertainty communication as a first-class concern

---

## What This Project Does Not Claim

This project does not claim to:
- Replace existing SIEM/SOAR tooling
- Solve the problem of AI model accuracy or bias in threat detection
- Provide a production-ready deployment
- Cover all regulatory requirements out of the box

It claims to demonstrate a *pattern* — a small, composable layer that can be placed between any AI recommendation engine and any human decision workflow to restore accountability, evidence, and auditability.

---

## Target Users

| User | Problem Being Solved |
|---|---|
| **SOC Analyst** | No structured way to document their reasoning or override an AI recommendation in the existing workflow |
| **SOC Manager / IR Lead** | Cannot reconstruct post-incident what the AI recommended, how confident it was, or why the analyst acted as they did |
| **Compliance / Audit Function** | Cannot demonstrate human oversight of automated security decisions to regulators |
| **Security Architect** | No lightweight reference pattern for inserting accountability into AI-assisted security pipelines |
