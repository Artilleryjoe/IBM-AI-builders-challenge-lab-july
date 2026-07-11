"""
dal_engine.py

Orchestration layer for the Decision Assurance Layer.
Ties together scenario loading, AI generation, record creation, and persistence.
Contains no UI logic — all functions take and return plain Python dicts / objects.

Public API
----------
get_recommendation(scenario_id: str) -> dict
    Load a scenario fixture and return it combined with an AI recommendation.
    Result is suitable for direct use in Streamlit session_state.

get_ranked_actions(scenario_id: str) -> dict
    Load a scenario fixture and return a ranked list of all three possible
    response actions, each with an independent confidence score.

submit_decision(
    scenario_id, ai_result, analyst_action, analyst_rationale,
    override_description=None, analyst_id="analyst_01"
) -> DecisionRecord
    Build, hash, persist, and return a completed DecisionRecord.

get_audit_log() -> list[dict]
    Return all saved decision records for the audit log view.
    Each record is annotated with integrity verification fields:
        integrity_valid : bool   — True if stored hash matches recomputed hash
        computed_hash   : str    — the freshly recomputed SHA-256 digest
        stored_hash     : str    — the hash that was written at save time
"""

from __future__ import annotations

import logging
from typing import Optional

from src import cos_client, scenario_loader, watsonx_client
from src.decision_record import DecisionRecord

logger = logging.getLogger(__name__)


def get_recommendation(scenario_id: str) -> dict:
    """
    Load the scenario fixture and generate an AI recommendation.

    Parameters
    ----------
    scenario_id : str
        The scenario ID (e.g. "scenario_001").

    Returns
    -------
    dict with keys:
        scenario      dict    The full scenario fixture
        recommendation str    "investigate" | "escalate" | "dismiss"
        confidence_score float
        reasoning     str
        suggested_actions list[str]
        source        str     "watsonx" | "mock" | "parse_error_fallback"
        error         str | None  Set if the scenario was not found

    Raises
    ------
    Does not raise — returns an error key in the dict on failure.
    """
    scenario = scenario_loader.get_scenario(scenario_id)
    if scenario is None:
        logger.error("[dal_engine] Scenario not found: %s", scenario_id)
        return {"error": f"Scenario '{scenario_id}' not found."}

    ai_result = watsonx_client.generate_recommendation(scenario)

    return {
        "scenario": scenario,
        "recommendation": ai_result["recommendation"],
        "confidence_score": ai_result["confidence_score"],
        "reasoning": ai_result["reasoning"],
        "suggested_actions": ai_result["suggested_actions"],
        "source": ai_result.get("source", "unknown"),
        "error": None,
    }


def submit_decision(
    scenario_id: str,
    ai_result: dict,
    analyst_action: str,
    analyst_rationale: str,
    override_description: Optional[str] = None,
    analyst_id: str = "analyst_01",
) -> DecisionRecord:
    """
    Create, hash, and persist a DecisionRecord from the analyst's decision.

    Parameters
    ----------
    scenario_id : str
        ID of the scenario this decision relates to.
    ai_result : dict
        The dict returned by get_recommendation() (or from session_state).
    analyst_action : str
        One of "approve", "reject", "override".
    analyst_rationale : str
        The analyst's documented reasoning (must be non-empty).
    override_description : str | None
        Required when analyst_action == "override".
    analyst_id : str
        Analyst identifier (stubbed in MVP).

    Returns
    -------
    DecisionRecord
        The completed, hashed, and persisted decision record.

    Raises
    ------
    ValueError
        If analyst_action is invalid, rationale is empty, or override_description
        is missing when action is "override".
    """
    # --- Validate inputs ---
    valid_actions = {"approve", "reject", "override"}
    if analyst_action not in valid_actions:
        raise ValueError(
            f"analyst_action must be one of {valid_actions}, got: {analyst_action!r}"
        )
    if not analyst_rationale or not analyst_rationale.strip():
        raise ValueError("analyst_rationale must not be empty.")
    if analyst_action == "override" and not (override_description or "").strip():
        raise ValueError(
            "override_description is required when analyst_action is 'override'."
        )

    # --- Resolve scenario title ---
    scenario = scenario_loader.get_scenario(scenario_id)
    scenario_title = scenario.get("title", scenario_id) if scenario else scenario_id

    # --- Build and persist the record ---
    record = DecisionRecord.create(
        scenario_id=scenario_id,
        scenario_title=scenario_title,
        ai_recommendation=ai_result.get("recommendation", ""),
        ai_confidence=float(ai_result.get("confidence_score", 0.0)),
        ai_reasoning=ai_result.get("reasoning", ""),
        ai_suggested_actions=list(ai_result.get("suggested_actions", [])),
        analyst_id=analyst_id,
        analyst_action=analyst_action,
        analyst_rationale=analyst_rationale.strip(),
        override_description=override_description.strip() if override_description else None,
    )

    cos_client.save_decision_record(record)
    logger.info(
        "[dal_engine] Decision record saved — id=%s action=%s hash=%s...",
        record.record_id, analyst_action, record.record_hash[:12],
    )

    return record


def get_audit_log() -> list[dict]:
    """
    Return all saved decision records for display in the audit log.

    Each returned dict is the full stored record augmented with three
    integrity-verification fields so the UI can display tamper status
    without performing its own crypto:

        integrity_valid : bool   True if the record has not been modified
                                  since it was originally saved.
        computed_hash   : str    SHAKE-256 (or SHA-256 for legacy) digest recomputed
                                  now from the stored fields (excluding record_hash).
        stored_hash     : str    The hash value written at save time.

    Returns
    -------
    list[dict]
        List of annotated DecisionRecord dicts, newest first.
        Returns an empty list if no records exist or if retrieval fails.
    """
    try:
        raw_records = cos_client.list_decision_records()
    except Exception as exc:
        logger.warning("[dal_engine] Could not retrieve audit log: %s", exc)
        return []

    annotated = []
    for record in raw_records:
        stored_hash = record.get("record_hash", "")
        computed_hash = DecisionRecord.compute_hash_for_dict(record)
        integrity_valid = (
            bool(computed_hash)
            and bool(stored_hash)
            and computed_hash == stored_hash
        )
        annotated_record = dict(record)
        annotated_record["integrity_valid"] = integrity_valid
        annotated_record["computed_hash"] = computed_hash
        annotated_record["stored_hash"] = stored_hash
        if not integrity_valid:
            logger.warning(
                "[dal_engine] Integrity check FAILED for record %s — "
                "stored=%s... computed=%s...",
                record.get("record_id", "?")[:8],
                stored_hash[:12] if stored_hash else "MISSING",
                computed_hash[:12] if computed_hash else "ERROR",
            )
        annotated.append(annotated_record)

    return annotated


def get_ranked_actions(scenario_id: str) -> dict:
    """
    Load the scenario fixture and return a ranked list of all three response
    actions, each scored independently by the AI.

    Parameters
    ----------
    scenario_id : str
        The scenario ID (e.g. "scenario_001").

    Returns
    -------
    dict with keys:
        scenario       dict        The full scenario fixture
        ranked_actions list[dict]  Sorted highest-confidence-first. Each item:
            action           str    "investigate" | "escalate" | "dismiss"
            confidence_score float  0.0 – 1.0
            reasoning        str    why this action scores as it does
            suggested_steps  list   2–3 specific steps for this action
        source         str         "watsonx" | "mock"
        error          str | None  Set if the scenario was not found
    """
    scenario = scenario_loader.get_scenario(scenario_id)
    if scenario is None:
        logger.error("[dal_engine] Scenario not found for ranked actions: %s", scenario_id)
        return {"error": f"Scenario '{scenario_id}' not found."}

    ranked = watsonx_client.generate_ranked_actions(scenario)
    source = ranked[0].get("source", "mock") if ranked else "mock"
    # source is not stored per-item in ranked response — infer from demo mode
    source = "mock" if watsonx_client.is_demo_mode() else "watsonx"

    return {
        "scenario": scenario,
        "ranked_actions": ranked,
        "source": source,
        "error": None,
    }


def is_demo_mode() -> bool:
    """
    Return True if either IBM service (watsonx or COS) is running in demo mode.
    Used by the UI to show the demo mode banner.
    """
    return watsonx_client.is_demo_mode() or cos_client.is_demo_mode()
