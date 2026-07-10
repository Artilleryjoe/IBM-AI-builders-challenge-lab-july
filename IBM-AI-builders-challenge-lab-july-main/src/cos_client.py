"""
cos_client.py

Wraps the IBM Cloud Object Storage SDK (ibm-cos-sdk-python / ibm_boto3) to
persist and list DecisionRecord objects.

Public API
----------
save_decision_record(record: DecisionRecord) -> str
    Upload the record to COS (or local fallback). Returns the storage key.

list_decision_records() -> list[dict]
    Return all saved decision records as a list of dicts.

is_demo_mode() -> bool
    True when COS credentials are absent and the local fallback is active.

If IBM COS credentials are absent or the SDK init fails, all calls route to a
local file fallback under data/decisions/ automatically.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from src.decision_record import DecisionRecord

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local fallback path
# ---------------------------------------------------------------------------

_LOCAL_DECISIONS_DIR = Path(__file__).parent.parent / "data" / "decisions"


def _ensure_local_dir() -> None:
    _LOCAL_DECISIONS_DIR.mkdir(parents=True, exist_ok=True)


def fallback_local_save(record: "DecisionRecord") -> str:
    """Save a DecisionRecord JSON file to data/decisions/ on disk."""
    _ensure_local_dir()
    key = f"decisions/{record.record_id}.json"
    dest = _LOCAL_DECISIONS_DIR / f"{record.record_id}.json"
    dest.write_text(record.to_json(), encoding="utf-8")
    logger.info("[cos_client] Record saved locally: %s", dest)
    return key


def fallback_local_list() -> list[dict]:
    """Return all decision records from data/decisions/ as a list of dicts."""
    _ensure_local_dir()
    records = []
    for path in sorted(_LOCAL_DECISIONS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            records.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("[cos_client] Skipping %s: %s", path.name, exc)
    return records


# ---------------------------------------------------------------------------
# IBM COS client (lazy-initialised)
# ---------------------------------------------------------------------------

_cos_client = None
_bucket: str = ""
_demo_mode: bool = False


def _get_cos_client():
    """
    Lazily initialise the ibm_boto3 COS client.
    Sets _demo_mode = True if credentials are missing or init fails.
    """
    global _cos_client, _bucket, _demo_mode

    if _cos_client is not None or _demo_mode:
        return _cos_client

    api_key = os.getenv("COS_API_KEY", "").strip()
    instance_crn = os.getenv("COS_INSTANCE_CRN", "").strip()
    endpoint = os.getenv("COS_ENDPOINT", "").strip()
    bucket = os.getenv("COS_BUCKET_NAME", "").strip()

    if not api_key or not instance_crn or not endpoint or not bucket:
        logger.warning(
            "[cos_client] COS credentials not fully set — "
            "running in demo mode with local file fallback."
        )
        _demo_mode = True
        return None

    try:
        import ibm_boto3
        from ibm_botocore.client import Config

        _cos_client = ibm_boto3.client(
            "s3",
            ibm_api_key_id=api_key,
            ibm_service_instance_id=instance_crn,
            config=Config(signature_version="oauth"),
            endpoint_url=endpoint,
        )
        _bucket = bucket
        logger.info("[cos_client] IBM COS client initialised — bucket: %s", bucket)
        return _cos_client

    except Exception as exc:
        logger.warning(
            "[cos_client] Failed to initialise IBM COS client (%s) — "
            "falling back to local file storage.", exc
        )
        _demo_mode = True
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_decision_record(record: "DecisionRecord") -> str:
    """
    Persist a DecisionRecord to IBM COS (or local fallback).

    Parameters
    ----------
    record : DecisionRecord
        A fully-populated record with record_hash already computed.

    Returns
    -------
    str
        The storage key: "decisions/{record_id}.json"
    """
    client = _get_cos_client()

    if client is None:
        return fallback_local_save(record)

    key = f"decisions/{record.record_id}.json"
    body = record.to_json().encode("utf-8")

    try:
        client.put_object(
            Bucket=_bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
        logger.info("[cos_client] Record uploaded to COS: s3://%s/%s", _bucket, key)
        return key

    except Exception as exc:
        logger.warning(
            "[cos_client] COS upload failed (%s) — saving locally instead.", exc
        )
        return fallback_local_save(record)


def list_decision_records() -> list[dict]:
    """
    Return all saved decision records as a list of dicts, newest first.

    Fetches from IBM COS (or local fallback). Each dict is the full
    DecisionRecord JSON payload.
    """
    client = _get_cos_client()

    if client is None:
        records = fallback_local_list()
        # newest first
        return sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)

    try:
        response = client.list_objects_v2(Bucket=_bucket, Prefix="decisions/")
        objects = response.get("Contents", [])

        records = []
        for obj in objects:
            key = obj["Key"]
            if not key.endswith(".json"):
                continue
            try:
                body = client.get_object(Bucket=_bucket, Key=key)["Body"].read()
                records.append(json.loads(body.decode("utf-8")))
            except Exception as fetch_exc:
                logger.warning("[cos_client] Could not fetch %s: %s", key, fetch_exc)

        return sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)

    except Exception as exc:
        logger.warning(
            "[cos_client] COS list failed (%s) — falling back to local records.", exc
        )
        records = fallback_local_list()
        return sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)


def is_demo_mode() -> bool:
    """Return True if running without live IBM COS credentials."""
    _get_cos_client()   # ensure initialisation has run
    return _demo_mode
