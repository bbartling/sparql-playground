from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _default_defs_path() -> Path:
    """Locate vendored defs whether package lives at repo-root src/ or a blog checkpoint."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "haystack" / "defs.json"
        if candidate.is_file():
            return candidate
    return Path.cwd() / "data" / "haystack" / "defs.json"


_DEFAULT_DEFS = _default_defs_path()

# Tree levels in the model UI → which def symbols are legal to apply.
LEVEL_MARKERS: dict[str, frozenset[str]] = {
    "site": frozenset({"site"}),
    "building": frozenset({"site", "building"}),
    "floor": frozenset({"floor", "space", "level"}),
    "equip": frozenset(
        {
            "equip",
            "ahu",
            "vav",
            "fan",
            "pump",
            "boiler",
            "chiller",
            "coolTower",
            "meter",
            "motor",
            "damper",
            "coil",
            "filter",
            "airHandlingEquip",
            "airTerminalUnit",
        }
    ),
    "part": frozenset(
        {
            "equip",
            "fan",
            "damper",
            "coil",
            "filter",
            "motor",
            "pump",
        }
    ),
    "point": frozenset(
        {
            "point",
            "sensor",
            "sp",
            "cmd",
            "his",
            "temp",
            "pressure",
            "flow",
            "humidity",
            "co2",
            "occupancy",
            "power",
            "energy",
            "voltage",
            "current",
            "air",
            "water",
            "steam",
            "discharge",
            "return",
            "outside",
            "exhaust",
            "mixed",
            "entering",
            "leaving",
            "zone",
            "duct",
            "pipe",
            "hot",
            "chilled",
            "cool",
            "heat",
            "speed",
            "enable",
            "run",
            "status",
            "alarm",
        }
    ),
}


def _sym(value: Any) -> str | None:
    if isinstance(value, dict) and value.get("_kind") == "symbol":
        text = value.get("val")
        return str(text) if text is not None else None
    if isinstance(value, str) and value:
        return value
    return None


def _is_list(row: dict[str, Any]) -> list[str]:
    raw = row.get("is")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [s for s in (_sym(x) for x in raw) if s]
    one = _sym(raw)
    return [one] if one else []


@lru_cache(maxsize=1)
def load_defs_index(path: str | None = None) -> dict[str, dict[str, str]]:
    """Map symbol → {doc, kind} from vendored defs.json."""
    defs_path = Path(path) if path else _default_defs_path()
    if not defs_path.is_file():
        raise FileNotFoundError(f"Haystack defs not found: {defs_path}")
    grid = json.loads(defs_path.read_text(encoding="utf-8"))
    rows = grid.get("rows") or []
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _sym(row.get("def"))
        if not name:
            continue
        kinds = _is_list(row)
        kind = "marker" if "marker" in kinds else (kinds[0] if kinds else "def")
        doc = str(row.get("doc") or "").strip()
        index[name] = {"doc": doc, "kind": kind}
    # Ensure UI level seeds exist even if taxonomy shifts.
    for bucket in LEVEL_MARKERS.values():
        for name in bucket:
            index.setdefault(name, {"doc": "", "kind": "marker"})
    return index


def catalog_for_level(level: str, *, path: str | None = None) -> dict[str, str]:
    """Return {symbol: doc} allowed for a tree level."""
    key = level.strip().lower()
    allowed = LEVEL_MARKERS.get(key)
    if allowed is None:
        raise ValueError(f"unknown level: {level}")
    index = load_defs_index(path)
    return {name: index.get(name, {}).get("doc", "") for name in sorted(allowed)}


def corpus_for_level(level: str, *, path: str | None = None) -> list[str]:
    return sorted(catalog_for_level(level, path=path))
