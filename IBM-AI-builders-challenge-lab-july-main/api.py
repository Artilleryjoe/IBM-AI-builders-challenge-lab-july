"""
api.py — Decision Assurance Layer: FastAPI REST API

Exposes the DAL engine as a REST API so the full workflow can be driven
programmatically — useful for integration testing, pipeline integration,
and CLI use via curl/httpx.

Run with:
    uvicorn api:app --reload

Or directly:
    python api.py

Endpoints
---------
GET  /health                              Liveness check + service mode status
GET  /scenarios                           List all available scenario IDs and titles
GET  /scenarios/{scenario_id}             Get a single scenario fixture
POST /recommendations/{scenario_id}       Generate an AI recommendation
POST /ranked-actions/{scenario_id}        Get ranked confidence scores for all 3 actions
POST /decisions                           Submit an analyst decision, save and return record
GET  /audit                               List all saved decision records (with integrity)
GET  /audit/{record_id}                   Get a single decision record by ID
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src import cos_client, dal_engine, scenario_loader, watsonx_client

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Decision Assurance Layer API",
    description=(
        "REST API for the IBM AI Builders Challenge Decision Assurance Layer prototype. "
        "Wraps IBM watsonx.ai (Granite) for AI recommendations and IBM Cloud Object Storage "
        "for immutable audit record persistence."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DecisionRequest(BaseModel):
    """Body for POST /decisions"""
    scenario_id: str = Field(..., description="ID of the scenario (e.g. 'scenario_001')")
    analyst_action: str = Field(
        ...,
        description="Analyst decision: 'approve', 'reject', or 'override'",
        pattern="^(approve|reject|override)$",
    )
    analyst_rationale: str = Field(
        ...,
        min_length=1,
        description="Documented rationale for the decision (required)",
    )
    override_description: Optional[str] = Field(
        default=None,
        description="Required when analyst_action is 'override' — describe the alternative action",
    )
    analyst_id: str = Field(
        default="analyst_01",
        description="Analyst identifier (stubbed in MVP)",
    )
    # AI result fields — pass through from a prior /recommendations call
    ai_recommendation: str = Field(
        default="",
        description="AI recommendation from a prior /recommendations call",
    )
    ai_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="AI confidence score from a prior /recommendations call",
    )
    ai_reasoning: str = Field(
        default="",
        description="AI reasoning from a prior /recommendations call",
    )
    ai_suggested_actions: List[str] = Field(
        default_factory=list,
        description="AI suggested actions from a prior /recommendations call",
    )


class HealthResponse(BaseModel):
    status: str
    ai_mode: str
    storage_mode: str
    scenarios_loaded: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mode_label(demo: bool, service: str) -> str:
    return f"{service} (demo/mock)" if demo else f"{service} (live)"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Liveness check. Reports AI and storage mode (live IBM vs demo/mock)."""
    return HealthResponse(
        status="ok",
        ai_mode=_mode_label(watsonx_client.is_demo_mode(), "IBM watsonx.ai Granite"),
        storage_mode=_mode_label(cos_client.is_demo_mode(), "IBM Cloud Object Storage"),
        scenarios_loaded=len(scenario_loader.list_scenarios()),
    )


@app.get("/scenarios", tags=["Scenarios"])
def list_scenarios():
    """Return all available scenario IDs and titles."""
    return {
        "scenarios": [
            {"id": s["id"], "title": s.get("title", ""), "severity": s.get("severity", "")}
            for s in scenario_loader.list_scenarios()
        ]
    }


@app.get("/scenarios/{scenario_id}", tags=["Scenarios"])
def get_scenario(scenario_id: str = Path(..., description="Scenario ID, e.g. 'scenario_001'")):
    """Return the full scenario fixture for the given ID."""
    scenario = scenario_loader.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")
    return scenario


@app.post("/recommendations/{scenario_id}", tags=["AI"])
def get_recommendation(
    scenario_id: str = Path(..., description="Scenario ID, e.g. 'scenario_001'"),
):
    """
    Generate a structured AI recommendation for the given scenario.

    Returns the top recommendation, confidence score, reasoning, and suggested actions.
    """
    result = dal_engine.get_recommendation(scenario_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    # Strip the full scenario object from the API response to keep it concise
    return {
        "scenario_id": scenario_id,
        "recommendation": result["recommendation"],
        "confidence_score": result["confidence_score"],
        "reasoning": result["reasoning"],
        "suggested_actions": result["suggested_actions"],
        "source": result["source"],
    }


@app.post("/ranked-actions/{scenario_id}", tags=["AI"])
def get_ranked_actions(
    scenario_id: str = Path(..., description="Scenario ID, e.g. 'scenario_001'"),
):
    """
    Get confidence scores for all three possible response actions.

    Returns a ranked list (highest confidence first) with per-action reasoning
    and suggested steps.
    """
    result = dal_engine.get_ranked_actions(scenario_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "scenario_id": scenario_id,
        "ranked_actions": result["ranked_actions"],
        "source": result["source"],
    }


@app.post("/decisions", tags=["Decisions"], status_code=201)
def submit_decision(body: DecisionRequest):
    """
    Submit an analyst decision, create a DecisionRecord, and persist it.

    The record is SHA-256 hashed before saving. Returns the full saved record
    including the record_id, timestamp, and record_hash for verification.

    Typical workflow:
        1. POST /recommendations/{scenario_id}  — get AI recommendation
        2. POST /decisions                       — submit analyst decision
        3. GET  /audit/{record_id}              — verify the saved record
    """
    # Validate override requirement server-side (pydantic regex covers action values)
    if body.analyst_action == "override" and not (body.override_description or "").strip():
        raise HTTPException(
            status_code=422,
            detail="override_description is required when analyst_action is 'override'.",
        )

    ai_result = {
        "recommendation": body.ai_recommendation,
        "confidence_score": body.ai_confidence,
        "reasoning": body.ai_reasoning,
        "suggested_actions": body.ai_suggested_actions,
    }

    try:
        record = dal_engine.submit_decision(
            scenario_id=body.scenario_id,
            ai_result=ai_result,
            analyst_action=body.analyst_action,
            analyst_rationale=body.analyst_rationale,
            override_description=body.override_description,
            analyst_id=body.analyst_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Storage error: {exc}")

    return JSONResponse(
        status_code=201,
        content=record.to_dict(),
    )


@app.get("/audit", tags=["Audit"])
def list_audit_log(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum records to return"),
):
    """
    Return saved decision records, newest first, with integrity verification.

    Each record includes integrity_valid, computed_hash, and stored_hash fields
    so callers can verify tamper-evidence programmatically.
    """
    records = dal_engine.get_audit_log()
    return {
        "total": len(records),
        "records": records[:limit],
    }


@app.get("/audit/{record_id}", tags=["Audit"])
def get_audit_record(
    record_id: str = Path(..., description="Full UUID record ID"),
):
    """
    Return a single decision record by ID, with integrity verification.

    Returns 404 if the record does not exist in the current storage backend.
    """
    all_records = dal_engine.get_audit_log()
    record = next((r for r in all_records if r.get("record_id") == record_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found.")
    return record


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DAL_API_PORT", "8000"))
    logger.info("Starting DAL API on port %d", port)
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
