"""
app.py — Decision Assurance Layer: SOC Analyst Workbench

Run with:
    streamlit run app.py

No .env file required — the app runs fully in Demo Mode (mock AI + local file
storage) when IBM credentials are absent.
"""

import json
import logging

import streamlit as st
from dotenv import load_dotenv

from src import cos_client, dal_engine, scenario_loader

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
if "jump_to_audit" not in st.session_state:
    st.session_state.jump_to_audit = False     # flag to highlight Audit Log after save
if "ranked_result" not in st.session_state:
    st.session_state.ranked_result = None      # dict from dal_engine.get_ranked_actions


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
    st.session_state.jump_to_audit = False
    st.session_state.ranked_result = None


# ---------------------------------------------------------------------------
# Sidebar — scenario selector + status indicators
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🛡️ DAL Workbench")
    st.caption("Decision Assurance Layer — IBM AI Builders Challenge")
    st.divider()

    # --- AI status ---
    from src import watsonx_client
    if watsonx_client.is_demo_mode():
        st.info("🤖 **AI:** Demo Mode (mock responses)")
    else:
        st.success("🤖 **AI:** IBM watsonx.ai (Granite)")

    # --- Storage status (requirement 8) ---
    if cos_client.is_demo_mode():
        local_path = cos_client.local_decisions_path()
        st.warning(f"💾 **Storage:** Local Demo Mode\n\n`{local_path}`")
    else:
        st.success("💾 **Storage:** IBM Cloud Object Storage")

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
    sev = scenario.get("severity", "?")
    st.markdown(
        f"**Severity:** <span style='color:{_severity_colour(sev)};font-weight:700'>{sev}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**Type:** {scenario.get('alert_type', '?')}")
    st.markdown(f"**MITRE:** `{scenario.get('mitre_tactic', '?')}`")
    st.markdown(f"**Technique:** `{scenario.get('mitre_technique', '?')}`")
    st.divider()
    st.caption(f"Source: `{scenario.get('source_ip','?')}`")
    st.caption(f"Destination: `{scenario.get('destination_ip','?')}`")
    st.caption(f"Host: `{scenario.get('affected_host','?')}`")
    st.caption(f"Time: `{scenario.get('timestamp','?')}`")


# ---------------------------------------------------------------------------
# Main area — tabs
# ---------------------------------------------------------------------------

# When the analyst just saved a record, default the tab index to Audit Log
default_tab = 1 if st.session_state.jump_to_audit else 0

tab_workbench, tab_ranked, tab_audit = st.tabs([
    "🔍 Analyst Workbench",
    "📊 Ranked Actions",
    "📋 Audit Log",
])

# ============================================================
# TAB 1 — Analyst Workbench
# ============================================================
with tab_workbench:

    st.header(f"🚨 {scenario.get('title', selected_id)}")

    # ----------------------------------------------------------------
    # Confirmation view — shown after a successful submission
    # ----------------------------------------------------------------
    if st.session_state.show_confirmation and st.session_state.last_record:
        rec = st.session_state.last_record
        action_html = _action_badge(rec.analyst_action)

        st.success("✅ Decision record saved successfully.")

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Action:** {action_html}", unsafe_allow_html=True)
            st.markdown(f"**Record ID:** `{rec.record_id}`")
            st.markdown(f"**Timestamp:** `{rec.timestamp}`")
        with col_b:
            if cos_client.is_demo_mode():
                local_file = cos_client.local_decisions_path() / f"{rec.record_id}.json"
                st.markdown(f"**Saved to:** Local fallback")
                st.code(str(local_file), language=None)
            else:
                st.markdown(f"**Saved to:** IBM Cloud Object Storage")
                st.code(f"decisions/{rec.record_id}.json", language=None)

        st.markdown(f"**SHA-256 Hash:**")
        st.code(rec.record_hash, language=None)
        st.caption(
            "This hash was computed over the full record content before saving. "
            "Any subsequent modification to any field will produce a different hash."
        )

        st.info(
            "👉 Open the **📋 Audit Log** tab to see this record alongside all previous decisions.",
            icon="📋",
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔄 Analyse Another Scenario", type="primary", use_container_width=True):
                _reset_workbench()
                st.rerun()
        with col_btn2:
            if st.button("📋 Go to Audit Log", type="secondary", use_container_width=True):
                st.session_state.jump_to_audit = True
                st.rerun()

    # ----------------------------------------------------------------
    # Main workbench view
    # ----------------------------------------------------------------
    else:
        col_evidence, col_ai = st.columns([1, 1], gap="large")

        # ---- Left column: Raw Evidence ----
        with col_evidence:
            st.subheader("📂 Raw Evidence")
            st.caption(
                "Evidence captured at alert time. "
                "Review this independently before reading the AI recommendation."
            )
            evidence = scenario.get("raw_evidence", [])
            for i, entry in enumerate(evidence, 1):
                st.markdown(f"**{i}.** {entry}")

            context = scenario.get("context", {})
            if context:
                with st.expander("Additional Context", expanded=False):
                    for k, v in context.items():
                        st.markdown(f"- **{k.replace('_', ' ').title()}:** {v}")

        # ---- Right column: AI Recommendation + Decision Form ----
        with col_ai:
            st.subheader("🤖 AI Recommendation")

            if st.session_state.ai_result is None:
                st.info("Click **Get AI Recommendation** to analyse this scenario.")
                if st.button(
                    "🔍 Get AI Recommendation",
                    type="primary",
                    use_container_width=True,
                ):
                    with st.spinner("Analysing with IBM watsonx.ai (Granite)…"):
                        result = dal_engine.get_recommendation(selected_id)
                    if result.get("error"):
                        st.error(result["error"])
                    else:
                        st.session_state.ai_result = result
                        st.rerun()
            else:
                ai = st.session_state.ai_result

                # Recommendation + confidence badge
                rec_text = ai["recommendation"].upper()
                score = ai["confidence_score"]
                st.markdown(
                    f"### {rec_text} &nbsp;&nbsp; {_confidence_badge(score)}",
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

                # ---- Analyst decision form ----
                st.subheader("⚖️ Your Decision")
                st.caption(
                    "You are the decision-maker. Your judgment overrides the AI. "
                    "All fields marked required must be completed before submitting."
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
                    placeholder=(
                        "Explain your reasoning. "
                        "Why do you agree, disagree, or take a different action?"
                    ),
                    height=100,
                )

                # Override description — only shown when Override selected
                override_desc = None
                if action_choice == "Override":
                    override_desc = st.text_area(
                        "Override Description *(required for Override)*",
                        placeholder="Describe the specific alternative action you are taking.",
                        height=80,
                    )

                # --- Validation gate (requirement 9) ---
                missing = []
                if not rationale.strip():
                    missing.append("rationale")
                if action_choice == "Override" and not (override_desc or "").strip():
                    missing.append("override description")
                can_submit = len(missing) == 0

                if not can_submit:
                    st.caption(
                        f"⚠️ Complete the following before submitting: "
                        f"**{', '.join(missing)}**"
                    )

                col_submit, col_reset = st.columns([3, 1])
                with col_submit:
                    submit_clicked = st.button(
                        "💾 Submit Decision",
                        type="primary",
                        use_container_width=True,
                        disabled=not can_submit,
                    )
                with col_reset:
                    st.button(
                        "↩️ Reset",
                        on_click=_reset_workbench,
                        type="secondary",
                        use_container_width=True,
                    )

                if submit_clicked and can_submit:
                    try:
                        with st.spinner("Saving decision record…"):
                            record = dal_engine.submit_decision(
                                scenario_id=selected_id,
                                ai_result=ai,
                                analyst_action=action_choice.lower(),
                                analyst_rationale=rationale,
                                override_description=(
                                    override_desc if action_choice == "Override" else None
                                ),
                            )
                        st.session_state.last_record = record
                        st.session_state.show_confirmation = True
                        st.session_state.jump_to_audit = False
                        st.rerun()
                    except ValueError as exc:
                        st.error(f"❌ Validation error: {exc}")
                    except OSError as exc:
                        st.error(
                            f"❌ Storage error — could not write record to disk:\n\n{exc}"
                        )
                    except Exception as exc:
                        st.error(f"❌ Unexpected error saving record: {exc}")


# ============================================================
# TAB 2 — Ranked Actions
# ============================================================
with tab_ranked:
    st.header("📊 Ranked Action Analysis")
    st.caption(
        "The AI scores all three possible response actions independently — not just the top "
        "recommendation. This gives you the full decision landscape and makes the AI's "
        "uncertainty explicit before you decide."
    )

    if st.session_state.ranked_result is None:
        st.info("Click **Get Ranked Analysis** to score all three response actions for the selected scenario.")
        if st.button("📊 Get Ranked Analysis", type="primary", use_container_width=False, key="btn_ranked"):
            with st.spinner("Scoring all actions with IBM watsonx.ai (Granite)…"):
                ranked_result = dal_engine.get_ranked_actions(selected_id)
            if ranked_result.get("error"):
                st.error(ranked_result["error"])
            else:
                st.session_state.ranked_result = ranked_result
                st.rerun()
    else:
        rr = st.session_state.ranked_result
        ranked_actions = rr.get("ranked_actions", [])

        if rr.get("source") == "mock":
            st.caption("⚠️ Demo mode — AI scores are simulated.")

        # ---- Action score cards ----
        action_colours = {
            "escalate":    ("#ef4444", "🚨"),
            "investigate": ("#f59e0b", "🔎"),
            "dismiss":     ("#22c55e", "✅"),
        }

        for rank, item in enumerate(ranked_actions, 1):
            action = item.get("action", "")
            score = item.get("confidence_score", 0.0)
            reasoning = item.get("reasoning", "")
            steps = item.get("suggested_steps", [])
            colour, icon = action_colours.get(action, ("#6b7280", "•"))

            badge_html = (
                f'<span style="background:{colour};color:#fff;padding:3px 12px;'
                f'border-radius:4px;font-weight:700;font-size:0.9rem;">'
                f'{icon} {action.upper()}</span>'
            )
            rank_label = {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th")

            with st.container(border=True):
                col_label, col_score = st.columns([3, 1])
                with col_label:
                    st.markdown(
                        f"**#{rank} ({rank_label})** &nbsp; {badge_html}",
                        unsafe_allow_html=True,
                    )
                with col_score:
                    st.metric(label="Confidence", value=f"{score:.0%}")
                st.progress(score)
                st.markdown(f"**Reasoning:** {reasoning}")
                if steps:
                    st.markdown("**Suggested steps:**")
                    for step in steps:
                        st.markdown(f"- {step}")

        st.divider()

        # ---- Score comparison bar chart ----
        st.subheader("Confidence Score Comparison")
        if ranked_actions:
            import pandas as pd
            chart_data = pd.DataFrame(
                {
                    "Action": [a["action"].capitalize() for a in ranked_actions],
                    "Confidence": [a["confidence_score"] for a in ranked_actions],
                }
            ).set_index("Action")
            st.bar_chart(chart_data, color="#6366f1", height=220)

        st.divider()
        st.caption(
            "These scores represent the AI's independent assessment of each action's "
            "appropriateness for this specific alert. They are not additive — treat them "
            "as relative confidence weights, not probabilities. Your judgment as the analyst "
            "is the final decision authority."
        )
        st.button("↩️ Reset Ranked Analysis", on_click=lambda: st.session_state.update({"ranked_result": None}), type="secondary")



with tab_audit:
    st.header("📋 Audit Log")
    st.caption(
        "All saved decision records — fetched live from storage on every page load. "
        "Each record contains the full DAL evidence bundle, AI recommendation, "
        "analyst judgment, and a SHA-256 tamper-evident hash."
    )

    # Storage location note
    if cos_client.is_demo_mode():
        st.info(
            f"💾 Records are stored locally at: `{cos_client.local_decisions_path()}`  \n"
            "They persist across app restarts.",
            icon="💾",
        )
    else:
        st.info("💾 Records are stored in IBM Cloud Object Storage.", icon="☁️")

    if st.button("🔄 Refresh", key="refresh_log"):
        st.session_state.jump_to_audit = False
        st.rerun()

    # Always fetch from storage — never from session_state (requirement 6)
    records = dal_engine.get_audit_log()

    if not records:
        st.info(
            "No decision records saved yet. "
            "Complete a decision in the Analyst Workbench tab, "
            "then return here to see it."
        )
    else:
        st.caption(f"**{len(records)} record(s)** — newest first.")

        # ---- Summary table ----
        table_rows = []
        for r in records:
            if r.get("integrity_valid") is True:
                integrity_label = "✅ Verified"
            else:
                integrity_label = "❌ Hash mismatch"
            table_rows.append({
                "Record ID": r.get("record_id", "")[:8] + "…",
                "Scenario": r.get("scenario_title", ""),
                "Action": r.get("analyst_action", "").upper(),
                "AI Rec": r.get("ai_recommendation", "").upper(),
                "Confidence": f"{r.get('ai_confidence', 0):.0%}",
                "Timestamp (UTC)": r.get("timestamp", "")[:19].replace("T", " "),
                "Integrity": integrity_label,
                "Hash (first 16)": r.get("record_hash", "")[:16] + "…",
            })
        st.dataframe(table_rows, use_container_width=True)

        # ---- Full record inspector ----
        st.subheader("Full Record Inspector")
        record_ids = [r.get("record_id", "?") for r in records]

        # Pre-select the most recently saved record if we just came from submission
        default_inspect = 0
        if st.session_state.last_record:
            last_id = st.session_state.last_record.record_id
            if last_id in record_ids:
                default_inspect = record_ids.index(last_id)

        selected_rec_id = st.selectbox(
            "Select record to inspect",
            options=record_ids,
            index=default_inspect,
            format_func=lambda x: x[:8] + "…",
        )
        full_rec = next(
            (r for r in records if r.get("record_id") == selected_rec_id), None
        )

        if full_rec:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Record ID:** `{full_rec['record_id']}`")
                st.markdown(f"**Scenario:** {full_rec.get('scenario_title','')}")
                st.markdown(f"**Timestamp:** `{full_rec.get('timestamp','')}`")
                st.markdown(f"**Analyst ID:** `{full_rec.get('analyst_id','')}`")
            with col2:
                action_html = _action_badge(full_rec.get("analyst_action", ""))
                st.markdown(
                    f"**Analyst Action:** {action_html}", unsafe_allow_html=True
                )
                st.markdown(
                    f"**AI Recommendation:** "
                    f"{full_rec.get('ai_recommendation','').upper()}"
                )
                conf = full_rec.get("ai_confidence", 0)
                st.markdown(
                    f"**AI Confidence:** {_confidence_badge(conf)}",
                    unsafe_allow_html=True,
                )

            st.markdown(
                f"**Analyst Rationale:** {full_rec.get('analyst_rationale','')}"
            )
            if full_rec.get("override_description"):
                st.markdown(
                    f"**Override Description:** {full_rec['override_description']}"
                )
            st.markdown(f"**AI Reasoning:** {full_rec.get('ai_reasoning','')}")

            st.divider()
            # ---- Integrity verification panel ----
            st.divider()
            st.subheader("🔐 Integrity Verification")

            integrity_valid = full_rec.get("integrity_valid")
            stored_hash = full_rec.get("stored_hash", full_rec.get("record_hash", ""))
            computed_hash = full_rec.get("computed_hash", "")

            if integrity_valid is True:
                st.success(
                    "✅ **Record integrity verified** — the stored hash matches the "
                    "recomputed hash. This record has not been modified since it was saved.",
                    icon="✅",
                )
            else:
                st.error(
                    "❌ **Hash mismatch detected** — the recomputed hash does not match "
                    "the stored hash. One or more fields in this record have been modified "
                    "after the record was originally saved.",
                    icon="❌",
                )

            col_hash1, col_hash2 = st.columns(2)
            with col_hash1:
                st.markdown("**Stored hash** *(written at save time)*")
                st.code(stored_hash, language=None)
            with col_hash2:
                st.markdown("**Recomputed hash** *(computed now from stored fields)*")
                st.code(computed_hash, language=None)

            if integrity_valid is False and stored_hash and computed_hash:
                st.caption(
                    "The two hashes differ — at least one field in this record was "
                    "changed after it was saved. The stored hash was computed at the "
                    "moment of submission over all fields (excluding `record_hash` itself, "
                    "with keys sorted). Recomputing it now from the current field values "
                    "produces a different digest."
                )
            else:
                st.caption(
                    "The SHA-256 hash was computed at save time over all record fields "
                    "except `record_hash` itself, with keys sorted alphabetically. "
                    "Any post-save change to any field will produce a different digest."
                )

            with st.expander("Raw JSON Record"):
                st.code(json.dumps(full_rec, indent=2), language="json")
