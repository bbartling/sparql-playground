from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


def _default_defs_path() -> Path:
    """Locate the vendored pack from either a checkout or a blog checkpoint."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "haystack" / "defs.json"
        if candidate.is_file():
            return candidate
    return Path.cwd() / "data" / "haystack" / "defs.json"


# Contextual markers which are useful in the tree but do not all descend from
# equip/quantity/phenomenon. These are candidates, never invented definitions.
_CONTEXT = frozenset(
    {
        "air",
        "water",
        "steam",
        "elec",
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
        "damper",
        "valve",
        "fan",
        "coil",
        "filter",
        "pump",
        "motor",
    }
)
LEVEL_MARKERS: dict[str, frozenset[str]] = {
    "site": frozenset({"site"}),
    # Haystack site normally represents a building; 'building' is not a standard marker.
    "building": frozenset({"site"}),
    # 'level' means fluid fill level, not storey of a building.
    "floor": frozenset({"floor", "space"}),
    "space": frozenset({"space", "room", "zone", "hvac"}),
    "equip": _CONTEXT | frozenset({"equip", "ahu", "vav", "boiler", "chiller", "meter"}),
    "part": _CONTEXT | frozenset({"equip"}),
    "point": _CONTEXT
    | frozenset(
        {
            "point",
            "sensor",
            "sp",
            "cmd",
            "synthetic",
            "computed",
            "ml",
            "sim",
            "his",
            "cur",
            "writable",
            "hisTotalized",
            "temp",
            "pressure",
            "flow",
            "humidity",
            "co2",
            "occupancy",
            "power",
            "energy",
            "volt",
            "current",
            "speed",
            "enable",
            "run",
            "alarm",
            "delta",
            "effective",
            "occupied",
            "unocc",
        }
    ),
}
_TAG_NAME = re.compile(r"[a-z][a-zA-Z0-9]*\Z")


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


@lru_cache(maxsize=8)
def load_defs_index(path: str | None = None) -> dict[str, dict[str, Any]]:
    """Index real defs, resolving the complete 'is' ancestry to find value kinds.

    For example sensor -> pointFunction -> choice -> marker. Looking only at a
    def's immediate parent would incorrectly hide most useful marker tags.
    """
    defs_path = Path(path) if path else _default_defs_path()
    if not defs_path.is_file():
        raise FileNotFoundError(f"Haystack defs not found: {defs_path}")
    grid = json.loads(defs_path.read_text(encoding="utf-8"))
    rows = {
        name: row
        for row in grid.get("rows", [])
        if isinstance(row, dict) and (name := _sym(row.get("def")))
    }

    def ancestors(name: str, visiting: frozenset[str] = frozenset()) -> set[str]:
        if name in visiting:
            raise ValueError(f"cyclic Haystack definition: {name}")
        parents = set(_is_list(rows.get(name, {})))
        result = set(parents)
        for parent in parents:
            result.update(ancestors(parent, visiting | {name}))
        return result

    kinds = (
        "marker",
        "bool",
        "number",
        "str",
        "uri",
        "ref",
        "symbol",
        "date",
        "time",
        "dateTime",
        "coord",
        "list",
        "dict",
        "grid",
        "val",
    )
    index: dict[str, dict[str, Any]] = {}
    for name, row in rows.items():
        supers = ancestors(name)
        kind = next((k for k in kinds if k == name or k in supers), "def")
        index[name] = {
            "doc": str(row.get("doc") or "").strip(),
            "kind": kind,
            "supertypes": tuple(sorted(supers)),
            "enum": str(row.get("enum") or ""),
        }
    return index


def is_subtype(symbol: str, parent: str, *, path: str | None = None) -> bool:
    entry = load_defs_index(path).get(symbol)
    return bool(entry and (symbol == parent or parent in entry["supertypes"]))


def catalog_for_level(level: str, *, path: str | None = None) -> dict[str, str]:
    """Return actual marker tags applicable to the selected tree context.

    This is a curated editor catalog, not a complete Haystack conformance schema.
    Scalar/ref defs, conjunct names and missing symbols must never become markers.
    """
    key = level.strip().lower()
    key = "equip" if key == "equipment" else key
    if key not in LEVEL_MARKERS:
        raise ValueError(f"unknown level: {level}")
    index = load_defs_index(path)
    allowed = set(LEVEL_MARKERS[key])
    roots = {
        "equip": {"equip"},
        "part": {"equip"},
        "point": {"pointFunction", "quantity", "phenomenon"},
    }.get(key, set())
    for name, entry in index.items():
        if roots.intersection(entry["supertypes"]):
            allowed.add(name)
    return {
        name: index[name]["doc"]
        for name in sorted(allowed)
        if name in index and index[name]["kind"] == "marker" and _TAG_NAME.fullmatch(name)
    }


def corpus_for_level(level: str, *, path: str | None = None) -> list[str]:
    return sorted(catalog_for_level(level, path=path))
