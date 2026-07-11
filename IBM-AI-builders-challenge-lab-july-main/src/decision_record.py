"""
decision_record.py

Defines the DecisionRecord dataclass — the canonical output of the Decision Assurance Layer.
Every analyst decision produces one record. Records are hashed for tamper-evidence.

Integrity verification
----------------------
verify_record_dict(record_dict) -> bool
    Accepts a record loaded from JSON (e.g. from disk or COS), recomputes the
    SHA-256 hash using the same canonical method as compute_hash(), and returns
    True if the recomputed hash matches the stored record_hash field.

    This is the live tamper-detection mechanism: any field mutated after the
    record was originally saved will produce a different hash, returning False.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class DecisionRecord:
    """
    A single auditable decision record produced when a SOC analyst acts on an
    AI-generated threat recommendation.

    Fields
    ------
    record_id       : Unique identifier for this record (UUID4).
    scenario_id     : ID of the threat scenario fixture this decision relates to.
    scenario_title  : Human-readable title of the scenario.
    ai_recommendation : The action recommended by the AI (investigate / escalate / dismiss).
    ai_confidence   : AI-reported confidence score, float in [0.0, 1.0].
    ai_reasoning    : Explanation provided by the AI for its recommendation.
    ai_suggested_actions : List of specific actions the AI proposed.
    analyst_id      : Identifier of the analyst who made the decision (stubbed for MVP).
    analyst_action  : The analyst's decision: "approve", "reject", or "override".
    analyst_rationale : Free-text rationale entered by the analyst (required).
    override_description : If analyst_action == "override", describes the alternative action taken.
    timestamp       : UTC ISO-8601 timestamp when the record was created.
    record_hash     : SHA-256 hex digest of the record content (computed last, excludes itself).
    """

    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    scenario_title: str = ""
    ai_recommendation: str = ""
    ai_confidence: float = 0.0
    ai_reasoning: str = ""
    ai_suggested_actions: List[str] = field(default_factory=list)
    analyst_id: str = "analyst_01"  # stubbed for MVP
    analyst_action: str = ""        # "approve" | "reject" | "override"
    analyst_rationale: str = ""
    override_description: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    record_hash: str = field(default="", init=False)

    def compute_hash(self) -> str:
        """
        Compute a SHA-256 hash over all record fields except record_hash itself.
        Assign the result to self.record_hash and return it.

        The hash is computed over the canonical JSON serialization of the record
        (keys sorted, record_hash excluded), making it deterministic and
        tamper-evident: any post-save mutation of any field will invalidate the hash.
        """
        payload = self._to_dict_without_hash()
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        self.record_hash = digest
        return digest

    def to_json(self) -> str:
        """Return the full record as a JSON string (hash must be computed first)."""
        return json.dumps(asdict(self), sort_keys=True, indent=2, ensure_ascii=True)

    def to_dict(self) -> dict:
        """Return the full record as a plain dict."""
        return asdict(self)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_dict_without_hash(self) -> dict:
        d = asdict(self)
        d.pop("record_hash", None)
        return d

    # ------------------------------------------------------------------
    # Convenience factory
    # ------------------------------------------------------------------

    @staticmethod
    def verify_record_dict(record_dict: dict) -> bool:
        """
        Verify the integrity of a record loaded from persistent storage.

        Recomputes the SHA-256 hash over all fields in `record_dict` except
        `record_hash`, using the same canonical serialisation as `compute_hash()`
        (JSON with sorted keys, ASCII-safe encoding), and compares the result to
        the stored `record_hash` value.

        Parameters
        ----------
        record_dict : dict
            A decision record as loaded from JSON — either from `data/decisions/`
            or from IBM Cloud Object Storage.

        Returns
        -------
        bool
            True  — the record has not been modified since it was saved.
            False — at least one field differs from what was hashed at save time,
                    or the stored hash is missing / malformed.
        """
        stored_hash = record_dict.get("record_hash", "")
        if not stored_hash or len(stored_hash) != 64:
            return False

        # Build a copy without the hash field — mirrors _to_dict_without_hash()
        payload = {k: v for k, v in record_dict.items() if k != "record_hash"}
        try:
            serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
            computed = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        except (TypeError, ValueError):
            return False

        return computed == stored_hash

    @staticmethod
    def compute_hash_for_dict(record_dict: dict) -> str:
        """
        Compute and return the SHA-256 hash for a record dict without modifying it.

        Used by the audit log to surface both the stored hash and the recomputed
        hash side-by-side for display in the UI.

        Parameters
        ----------
        record_dict : dict
            A decision record as loaded from JSON.

        Returns
        -------
        str
            64-character hex SHA-256 digest, or an empty string on error.
        """
        payload = {k: v for k, v in record_dict.items() if k != "record_hash"}
        try:
            serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        except (TypeError, ValueError):
            return ""

    @classmethod
    def create(
        cls,
        scenario_id: str,
        scenario_title: str,
        ai_recommendation: str,
        ai_confidence: float,
        ai_reasoning: str,
        ai_suggested_actions: List[str],
        analyst_action: str,
        analyst_rationale: str,
        override_description: Optional[str] = None,
        analyst_id: str = "analyst_01",
    ) -> "DecisionRecord":
        """
        Factory that creates a DecisionRecord, computes its hash, and returns it
        ready to be saved.
        """
        record = cls(
            scenario_id=scenario_id,
            scenario_title=scenario_title,
            ai_recommendation=ai_recommendation,
            ai_confidence=ai_confidence,
            ai_reasoning=ai_reasoning,
            ai_suggested_actions=ai_suggested_actions,
            analyst_id=analyst_id,
            analyst_action=analyst_action,
            analyst_rationale=analyst_rationale,
            override_description=override_description,
        )
        record.compute_hash()
        return record
