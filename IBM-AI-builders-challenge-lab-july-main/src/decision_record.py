"""
decision_record.py

Defines the DecisionRecord dataclass — the canonical output of the Decision Assurance Layer.
Every analyst decision produces one record. Records are hashed for tamper-evidence.

Hash algorithm
--------------
Records are hashed using SHAKE-256 (SHA-3 family, NIST FIPS 202), producing a
256-bit / 64-character hex digest. SHAKE-256 is a post-quantum-resilient extendable
output function (XOF) that provides:

  - Quantum resistance: unlike SHA-256, SHAKE-256 is not vulnerable to
    Grover's algorithm halving the effective security level. A 256-bit SHAKE-256
    output retains ~256-bit preimage resistance against quantum adversaries.
  - Classical collision resistance equivalent to SHA-3/256.
  - NIST standardisation under FIPS 202 (2015) and included in NIST's
    post-quantum cryptography guidance.

The hash_algorithm field on every saved record declares which algorithm produced
the digest, ensuring records remain self-describing and verifiable as standards evolve.

Integrity verification
----------------------
verify_record_dict(record_dict) -> bool
    Accepts a record loaded from JSON (e.g. from disk or COS), recomputes the
    SHAKE-256 hash using the same canonical method as compute_hash(), and returns
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

# ---------------------------------------------------------------------------
# Algorithm constants — declared here so every layer of the system references
# a single source of truth rather than hard-coding algorithm names inline.
# ---------------------------------------------------------------------------

#: The hash algorithm used for all new DecisionRecord instances.
#: SHAKE-256 is a post-quantum-resilient XOF from the SHA-3 family (NIST FIPS 202).
HASH_ALGORITHM = "SHAKE-256"

#: Digest length in bytes — 32 bytes = 256 bits = 64 hex characters.
#: Identical wire format to SHA-256, so no downstream storage changes are needed.
_DIGEST_BYTES = 32


def _shake256_hex(data: bytes) -> str:
    """Compute a SHAKE-256 digest and return it as a 64-character hex string."""
    return hashlib.shake_256(data).hexdigest(_DIGEST_BYTES)


@dataclass
class DecisionRecord:
    """
    A single auditable decision record produced when a SOC analyst acts on an
    AI-generated threat recommendation.

    Fields
    ------
    record_id            : Unique identifier for this record (UUID4).
    scenario_id          : ID of the threat scenario fixture this decision relates to.
    scenario_title       : Human-readable title of the scenario.
    ai_recommendation    : The action recommended by the AI (investigate / escalate / dismiss).
    ai_confidence        : AI-reported confidence score, float in [0.0, 1.0].
    ai_reasoning         : Explanation provided by the AI for its recommendation.
    ai_suggested_actions : List of specific actions the AI proposed.
    analyst_id           : Identifier of the analyst who made the decision (stubbed for MVP).
    analyst_action       : The analyst's decision: "approve", "reject", or "override".
    analyst_rationale    : Free-text rationale entered by the analyst (required).
    override_description : If analyst_action == "override", the alternative action taken.
    timestamp            : UTC ISO-8601 timestamp when the record was created.
    hash_algorithm       : The algorithm used to compute record_hash (default: SHAKE-256).
    record_hash          : 64-char hex digest of the record content (computed last,
                           excludes itself, uses the algorithm named in hash_algorithm).
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
    hash_algorithm: str = field(default=HASH_ALGORITHM)
    record_hash: str = field(default="", init=False)

    def compute_hash(self) -> str:
        """
        Compute a SHAKE-256 hash over all record fields except record_hash itself.
        Assign the result to self.record_hash and return it.

        The hash is computed over the canonical JSON serialisation of the record
        (keys sorted, record_hash excluded), making it deterministic and
        post-quantum-resilient: any post-save mutation of any field will produce
        a different 64-char hex digest.

        The hash_algorithm field is included in the payload so the digest commits
        to the algorithm used — changing the algorithm would itself change the hash.
        """
        payload = self._to_dict_without_hash()
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        digest = _shake256_hex(serialized.encode("utf-8"))
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
    # Static verification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def verify_record_dict(record_dict: dict) -> bool:
        """
        Verify the integrity of a record loaded from persistent storage.

        Recomputes the hash over all fields in `record_dict` except `record_hash`,
        using the algorithm named in the record's `hash_algorithm` field.
        Currently supports SHAKE-256 (default) and SHA-256 (legacy records).

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

        computed = DecisionRecord.compute_hash_for_dict(record_dict)
        return bool(computed) and computed == stored_hash

    @staticmethod
    def compute_hash_for_dict(record_dict: dict) -> str:
        """
        Compute and return the hash for a record dict without modifying it.

        Respects the `hash_algorithm` field so legacy SHA-256 records and new
        SHAKE-256 records can both be verified correctly.

        Parameters
        ----------
        record_dict : dict
            A decision record as loaded from JSON.

        Returns
        -------
        str
            64-character hex digest, or an empty string on error.
        """
        payload = {k: v for k, v in record_dict.items() if k != "record_hash"}
        algorithm = record_dict.get("hash_algorithm", "SHA-256")
        try:
            serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
            data = serialized.encode("utf-8")
            if algorithm == "SHAKE-256":
                return _shake256_hex(data)
            elif algorithm == "SHA-256":
                # Legacy compatibility — records created before the PQC upgrade
                return hashlib.sha256(data).hexdigest()
            else:
                # Unknown algorithm — recompute with current default
                return _shake256_hex(data)
        except (TypeError, ValueError):
            return ""

    # ------------------------------------------------------------------
    # Convenience factory
    # ------------------------------------------------------------------

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
        Factory that creates a DecisionRecord, computes its SHAKE-256 hash,
        and returns it ready to be saved.
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
