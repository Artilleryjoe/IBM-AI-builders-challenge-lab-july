# Concept: Decision Assurance Layer for AI-Assisted Cybersecurity

## Thesis

> **Future cybersecurity is not AI autonomy. Future cybersecurity is accountable AI-assisted command and control.**

AI systems are increasingly embedded in Security Operations Centres (SOCs). They can process telemetry faster than any human analyst, correlate signals across thousands of endpoints simultaneously, and surface threat hypotheses in seconds. But speed without accountability is dangerous. When an AI-generated recommendation leads to an incorrect response — an asset taken offline unnecessarily, a real attack dismissed as a false positive, or a containment action that causes collateral damage — *who is responsible, and what evidence exists to review?*

The **Decision Assurance Layer (DAL)** is a software pattern and prototype that sits between AI-generated threat recommendations and human operator decisions. It does not replace the AI. It does not replace the analyst. It creates a structured, auditable record of every decision: what the AI recommended, how confident it was, what the human decided, why they decided it, and what happened as a result.

---

## The Core Problem

Modern SOC workflows increasingly look like this:

```
[Threat Alert] -> [AI Triage / Recommendation] -> [Analyst Action]
```

The AI step is often a black box. The analyst receives a recommendation with little visibility into:
- What evidence the AI weighted most heavily
- How confident the AI actually is (versus how confident it sounds)
- What alternative actions the AI considered and rejected
- Whether the analyst's override of a previous recommendation was ever recorded

This creates three compounding risks:

1. **Evidence loss** — The reasoning behind a decision evaporates. Post-incident reviews cannot reconstruct what was known at the time.
2. **Accountability gaps** — When an AI-assisted decision goes wrong, there is no record of the human judgment step. Liability is diffuse.
3. **Automation bias** — Without a structured moment of human judgment, analysts tend to rubber-stamp AI recommendations. The "human in the loop" becomes a formality.

---

## The Decision Assurance Layer

The DAL inserts a structured judgment checkpoint into the workflow:

```
[Threat Alert]
    |
    v
[AI Analysis - watsonx.ai / Granite]
    |
    v
[DAL: Evidence Bundle + Recommendation + Confidence Score]
    |
    v
[Human Analyst: Review -> Approve / Reject / Override + Rationale]
    |
    v
[Decision Record: Immutable, Hashed, Persisted to IBM Cloud Object Storage]
```

Each step is explicit. Each output is captured. The final record is tamper-evident.

---

## A Concrete Scenario

**Scenario:** A SOC analyst at a mid-size financial institution receives an alert. Their SIEM has flagged unusual SMB traffic from a finance workstation — a pattern consistent with lateral movement. An AI assistant has already analysed the alert and issued a recommendation.

**Without the DAL:**
The analyst sees: *"AI recommends: Investigate. Confidence: High."*
They approve it, escalate to IR, and move on. No record of what evidence the AI used. No record of the analyst's reasoning. If the escalation was wrong, there is nothing to review.

**With the DAL:**
The analyst sees a structured workbench:
- The raw evidence log (7 timestamped entries from EDR, proxy, and authentication systems)
- The AI's recommendation (*Escalate*), confidence score (*0.87 / 1.0*), reasoning summary, and 3 suggested actions
- A confidence badge coloured amber or red when the AI is uncertain
- A mandatory rationale field before any action can be submitted

The analyst reviews, agrees with the AI, types their reasoning, and clicks **Approve**. The DAL creates a `DecisionRecord` containing all of the above, computes a SHAKE-256 hash (post-quantum-resilient) of the record content, and persists it to IBM Cloud Object Storage. The record cannot be silently altered after the fact.

**The result:** A reviewable, auditable trail of exactly what was known, what was recommended, and what was decided — at the moment of decision.

---

## The Five DAL Elements

Every decision passing through the DAL is structured around five elements:

| Element | Description |
|---|---|
| **Evidence Bundle** | The raw threat data the AI analysed — timestamped log entries, IPs, hostnames, MITRE tactics |
| **AI Recommendation** | The action recommended (investigate / escalate / dismiss) with supporting reasoning |
| **Uncertainty Score** | A confidence score (0.0-1.0) that explicitly communicates AI uncertainty to the analyst |
| **Human Judgment** | The analyst's action (approve / reject / override), rationale, and override description |
| **Audit Record** | The immutable, SHAKE-256-hashed `DecisionRecord` persisted to IBM Cloud Object Storage |

These five elements are the schema backbone of the entire system. They appear in the data model, the UI, the documentation, and the framework.

---

## What This Prototype Demonstrates

This MVP prototype demonstrates the DAL concept as a working Streamlit application:

1. A SOC analyst selects a simulated threat scenario (lateral movement, ransomware precursor, or credential stuffing)
2. IBM watsonx.ai (Granite model) analyses the scenario and returns a structured recommendation with a confidence score
3. The analyst reviews the evidence and AI output in a structured workbench UI
4. The analyst approves, rejects, or overrides the recommendation — with a mandatory rationale
5. A `DecisionRecord` is created, hashed, and saved to IBM Cloud Object Storage
6. The Audit Log view shows all saved records, verifiable by their hash

The prototype is intentionally small. The value is not in the scale — it is in demonstrating that the pattern *works*, that it is *buildable*, and that it is *IBM-native*.
