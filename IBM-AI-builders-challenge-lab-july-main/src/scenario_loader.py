"""
scenario_loader.py

Loads threat scenario fixtures from data/scenarios/*.json.
Provides list_scenarios() and get_scenario(id) for use by the DAL engine and UI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

# Resolve path relative to this file so it works regardless of cwd
_SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def _load_all() -> Dict[str, dict]:
    """
    Read every *.json file in the scenarios directory and return a dict
    keyed by scenario id.  Results are cached in module-level state after
    the first call.
    """
    scenarios: Dict[str, dict] = {}
    if not _SCENARIOS_DIR.exists():
        return scenarios
    for path in sorted(_SCENARIOS_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            scenario_id = data.get("id", path.stem)
            scenarios[scenario_id] = data
        except (json.JSONDecodeError, OSError) as exc:
            # Log and skip malformed files — don't crash the whole app
            print(f"[scenario_loader] Skipping {path.name}: {exc}")
    return scenarios


# Module-level cache — loaded once per process
_cache: Optional[Dict[str, dict]] = None


def _get_cache() -> Dict[str, dict]:
    global _cache
    if _cache is None:
        _cache = _load_all()
    return _cache


def list_scenarios() -> List[dict]:
    """
    Return all loaded scenarios as a list, ordered by their id.

    Each entry is the full scenario dict as parsed from its JSON fixture.
    """
    return list(_get_cache().values())


def get_scenario(scenario_id: str) -> Optional[dict]:
    """
    Return the scenario dict for the given id, or None if not found.
    """
    return _get_cache().get(scenario_id)


def scenario_titles() -> Dict[str, str]:
    """
    Return a mapping of scenario_id -> title, useful for populating UI dropdowns.
    """
    return {sid: s.get("title", sid) for sid, s in _get_cache().items()}


def reload() -> None:
    """
    Force a reload from disk (useful in tests or if fixtures change at runtime).
    """
    global _cache
    _cache = None
    _get_cache()
