"""
app.py — Decision Assurance Layer: SOC Analyst Workbench

Run with:
    streamlit run app.py
"""

import logging

import streamlit as st
from dotenv import load_dotenv

from src import dal_engine, scenario_loader

load_dotenv()
logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Decision Assurance Layer — SOC Analyst Workbench",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None          # dict from dal_engine.get_recommendation
if "last_record" not in st.session_state:
    st.session_state.last_record = None        # DecisionRecord after submission
if "show_confirmation" not in st.session_state:
    st.session_state.show_confirmation = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _confidence_badge(score: float) -> str:
    """Return an HTML badge string coloured by confidence score."""
    if score >= 0.75:
        colour, label = "#22c55e", "HIGH"
    elif score >= 0.50:
        colour, label = "#f59e0b", "MEDIUM"
    else:
        colour, label = "#ef4444", "LOW"
    return (
        f'<span style="background:{colour};color:#fff;padding:3px 10px;'
        f'border-radius:4px;font-weight:600;font-size:0.85rem;">'
        f'{label} &nbsp;{score:.2f}</span>'
    )


def _action_badge(action: str) -> str:
    colours = {"approve": "#22c55e", "reject": "#ef4444", "override": "#f59e0b"}
    colour = colours.get(action.lower(), "#6b7280")
    return (
        f'<span style="background:{colour};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-weight:600;font-size:0.8rem;">'
        f'{action.upper()}</span>'
    )


def _severity_colour(severity: str) -> str:
    return {
        "CRITICAL": "#ef4444",
        "HIGH": "#f97316",
        "MEDIUM": "#f59e0b",
        "LOW": "#22c55e",
    }.get(severity.upper(), "#6b7280")


def _reset_workbench():
    st.session_state.ai_result = None
    st.session_state.last_record = None
    st.session_state.show_confirmation = False


# ---------------------------------------------------------------------------
# Sidebar — scenario selector
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🛡️ DAL Workbench")
    st.caption("Decision Assurance Layer — IBM AI Builders Challenge")
    st.divider()

    if dal_engine.is_demo_mode():
        st.warning("⚠️ **Demo Mode** — running without live IBM credentials. Mock AI responses and local file storage are active.")
        st.divider()

    titles = scenario_loader.scenario_titles()
    if not titles:
        st.error("No scenario fixtures found in data/scenarios/")
        st.stop()

    scenario_options = list(titles.keys())
    scenario_labels = [titles[k] for k in scenario_options]

    selected_index = st.selectbox(
        "Select Threat Scenario",
        options=range(len(scenario_options)),
        format_func=lambda i: scenario_labels[i],
        on_change=_reset_workbench,
    )
    selected_id = scenario_options[selected_index]
    scenario = scenario_loader.get_scenario(selected_id)

    st.divider()
    st.markdown(f"**Severity:** <span style='color:{_severity_colour(scenario.get('severity',''))};font-weight:700'>{scenario.get('severity','?')}</span>", unsafe_allow_html=True)
    st.markdown(f"**Type:** {scenario.get('alert_type', '?')}")
    st.markdown(f"**MITRE:** `{scenario.get('mitre_tactic', '?')}`")
    st.markdown(f"**Technique:** `{scenario.get('mitre_technique', '?')}`")
    st.divider()
    st.caption(f"Source: `{scenario.get('source_ip','?')}`")
    st.caption(f"Destination: `{scenario.get('destination_ip','?')}`")
    st.caption(f"Host: `{scenario.get('affected_host','?')}`")
    st.caption(f"Time: `{scenario.get('timestamp','?')}`")


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

tab_workbench, tab_audit = st.tabs(["🔍 Analyst Workbench", "📋 Audit Log"])

# ============================================================
# TAB 1 — Analyst Workbench
# ============================================================
with tab_workbench:

    st.header(f"🚨 {scenario.get('title', selected_id)}")

    if st.session_state.show_confirmation and st.session_state.last_record:
        # ---- Confirmation banner ----
        rec = st.session_state.last_record
        action_html = _action_badge(rec.analyst_action)
        st.success("✅ Decision record saved successfully.")
        st.markdown(f"**Action:** {action_html}", unsafe_allow_html=True)
        st.markdown(f"**Record ID:** `{rec.record_id}`")
        st.markdown(f"**Timestamp:** `{rec.timestamp}`")
        st.markdown(
            f"**SHA-256 Hash:** `{rec.record_hash}`",
        )
        st.caption(
            "This hash was computed over the full record content before saving. "
            "Any subsequent modification to any field will invalidate it."
        )
        if st.button("🔄 Analyse Another Scenario", type="secondary"):
            _reset_workbench()
            st.rerun()

    else:
        # ---- Evidence + AI columns ----
        col_evidence, col_ai = st.columns([1, 1], gap="large")

        with col_evidence:
            st.subheader("📂 Raw Evidence")
            st.caption(
                "Evidence captured at alert time. Review this independently before reading the AI recommendation."
            )
            evidence = scenario.get("raw_evidence", [])
            for i, entry in enumerate(evidence, 1):
                st.markdown(f"**{i}.** {entry}")

            context = scenario.get("context", {})
            if context:
                with st.expander("Additional Context", expanded=False):
                    for k, v in context.items():
                        st.markdown(f"- **{k.replace('_', ' ').title()}:** {v}")

        with col_ai:
            st.subheader("🤖 AI Recommendation")

            if st.session_state.ai_result is None:
                st.info("Click **Get AI Recommendation** to analyse this scenario.")
                if st.button("🔍 Get AI Recommendation", type="primary", use_container_width=True):
                    with st.spinner("Analysing with IBM watsonx.ai (Granite)…"):
                        result = dal_engine.get_recommendation(selected_id)
                    if result.get("error"):
                        st.error(result["error"])
                    else:
                        st.session_state.ai_result = result
                        st.rerun()
            else:
                ai = st.session_state.ai_result

                # Recommendation + confidence
                rec_text = ai["recommendation"].upper()
                score = ai["confidence_score"]
                confidence_html = _confidence_badge(score)
                st.markdown(
                    f"### {rec_text} &nbsp;&nbsp; {confidence_html}",
                    unsafe_allow_html=True,
                )
                st.progress(score, text=f"AI Confidence: {score:.0%}")

                st.markdown("**Reasoning:**")
                st.markdown(f"> {ai['reasoning']}")

                st.markdown("**Suggested Actions:**")
                for action in ai.get("suggested_actions", []):
                    st.markdown(f"- {action}")

                if ai.get("source") == "mock":
                    st.caption("⚠️ Demo mode — AI response is simulated.")

                st.divider()

                # ---- Analyst action form ----
                st.subheader("⚖️ Your Decision")
                st.caption(
                    "You are the decision-maker. Your judgment overrides the AI. "
                    "This form is required before a decision record can be saved."
                )

                action_choice = st.radio(
                    "Decision",
                    options=["Approve", "Reject", "Override"],
                    horizontal=True,
                    help=(
                        "**Approve** — act on the AI recommendation as stated.  \n"
                        "**Reject** — dismiss the recommendation (document why).  \n"
                        "**Override** — take a different, specific action (document what)."
                    ),
                )

                rationale = st.text_area(
                    "Rationale *(required)*",
                    placeholder="Explain your reasoning. Why do you agree, disagree, or take a different action?",
                    height=100,
                )

                override_desc = None
                if action_choice == "Override":
                    override_desc = st.text_area(
                        "Override Description *(required for Override)*",
                        placeholder="Describe the specific alternative action you are taking.",
                        height=80,
                    )

                # Disable submit until rationale is filled (and override desc when needed)
                can_submit = bool(rationale.strip())
                if action_choice == "Override":
                    can_submit = can_submit and bool((override_desc or "").strip())

                if st.button(
                    "💾 Submit Decision",
                    type="primary",
                    use_container_width=True,
                    disabled=not can_submit,
                ):
                    try:
                        with st.spinner("Saving decision record…"):
                            record = dal_engine.submit_decision(
                                scenario_id=selected_id,
                                ai_result=ai,
                                analyst_action=action_choice.lower(),
                                analyst_rationale=rationale,
                                override_description=override_desc if action_choice == "Override" else None,
                            )
                        st.session_state.last_record = record
                        st.session_state.show_confirmation = True
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Validation error: {e}")
                    except Exception as e:
                        st.error(f"Unexpected error saving record: {e}")

                if not can_submit:
                    missing = []
                    if not rationale.strip():
                        missing.append("rationale")
                    if action_choice == "Override" and not (override_desc or "").strip():
                        missing.append("override description")
                    st.caption(f"Complete the following to submit: {', '.join(missing)}")

                st.button("↩️ Reset Recommendation", on_click=_reset_workbench, type="secondary")


# ============================================================
# TAB 2 — Audit Log
# ============================================================
with tab_audit:
    st.header("📋 Audit Log")
    st.caption(
        "All saved decision records. Each record contains the full DAL evidence bundle, "
        "AI recommendation, analyst judgment, and a SHA-256 tamper-evident hash."
    )

    if st.button("🔄 Refresh", key="refresh_log"):
        st.rerun()

    records = dal_engine.get_audit_log()

    if not records:
        st.info("No decision records saved yet. Complete a decision in the Analyst Workbench tab.")
    else:
        st.caption(f"{len(records)} record(s) found — newest first.")

        # Summary table
        table_rows = []
        for r in records:
            table_rows.append({
                "Record ID": r.get("record_id", "")[:8] + "…",
                "Scenario": r.get("scenario_title", ""),
                "Action": r.get("analyst_action", "").upper(),
                "AI Rec": r.get("ai_recommendation", "").upper(),
                "Confidence": f"{r.get('ai_confidence', 0):.0%}",
                "Timestamp (UTC)": r.get("timestamp", "")[:19].replace("T", " "),
                "Hash (first 16)": r.get("record_hash", "")[:16] + "…",
            })

        st.dataframe(table_rows, use_container_width=True)

        # Expandable full record view
        st.subheader("Full Record Inspector")
        record_ids = [r.get("record_id", "?") for r in records]
        selected_rec_id = st.selectbox("Select record to inspect", options=record_ids, format_func=lambda x: x[:8] + "…")
        full_rec = next((r for r in records if r.get("record_id") == selected_rec_id), None)
        if full_rec:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Record ID:** `{full_rec['record_id']}`")
                st.markdown(f"**Scenario:** {full_rec.get('scenario_title','')}")
                st.markdown(f"**Timestamp:** `{full_rec.get('timestamp','')}`")
                st.markdown(f"**Analyst ID:** `{full_rec.get('analyst_id','')}`")
            with col2:
                action_html = _action_badge(full_rec.get("analyst_action", ""))
                st.markdown(f"**Analyst Action:** {action_html}", unsafe_allow_html=True)
                st.markdown(f"**AI Recommendation:** {full_rec.get('ai_recommendation','').upper()}")
                conf = full_rec.get('ai_confidence', 0)
                st.markdown(f"**AI Confidence:** {_confidence_badge(conf)}", unsafe_allow_html=True)

            st.markdown(f"**Analyst Rationale:** {full_rec.get('analyst_rationale','')}")
            if full_rec.get("override_description"):
                st.markdown(f"**Override Description:** {full_rec['override_description']}")
            st.markdown(f"**AI Reasoning:** {full_rec.get('ai_reasoning','')}")

            st.divider()
            st.markdown(f"**SHA-256 Hash:** `{full_rec.get('record_hash','')}`")
            st.caption(
                "Verify integrity: re-compute SHA-256 over the record JSON (excluding the hash field, "
                "keys sorted) and compare with the stored hash above."
            )

            with st.expander("Raw JSON Record"):
                import json
                st.code(json.dumps(full_rec, indent=2), language="json")
