from __future__ import annotations

import difflib
import re
from typing import Any

from bldgts.haystack.defs import LEVEL_MARKERS, catalog_for_level, load_defs_index

_TOKEN = re.compile(r"[a-z0-9]+", re.I)

# FinStack / Niagara-style: pick at most one marker per role from the point name.
POINT_ROLES: dict[str, tuple[str, ...]] = {
    "entity": ("point",),
    "function": ("sensor", "sp", "cmd"),
    "substance": ("air", "water", "steam", "elec"),
    "section": (
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
    ),
    "quantity": (
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
        "speed",
        "position",
    ),
    "device": ("damper", "valve", "fan", "coil", "filter", "pump", "motor"),
    "history": ("his",),
}

# Alias tokens in BMS names → Haystack symbols.
_ALIASES: dict[str, str] = {
    "temperature": "temp",
    "temperatures": "temp",
    "tmp": "temp",
    "t": "temp",
    "static": "pressure",
    "press": "pressure",
    "dp": "pressure",
    "setpoint": "sp",
    "set": "sp",
    "setpt": "sp",
    "command": "cmd",
    "cmd": "cmd",
    "output": "cmd",
    "out": "cmd",
    "ao": "cmd",
    "bo": "cmd",
    "input": "sensor",
    "ai": "sensor",
    "bi": "sensor",
    "sa": "discharge",
    "da": "discharge",
    "supply": "discharge",
    "rat": "return",
    "ra": "return",
    "oa": "outside",
    "oat": "outside",
    "mat": "mixed",
    "ea": "exhaust",
    "sat": "discharge",
    "vfd": "speed",
    "damper": "damper",
    "dmp": "damper",
    "vlv": "valve",
    "valve": "valve",
}


def _normalize(text: str) -> str:
    return " ".join(_TOKEN.findall(text.lower()))


def _score_symbol(query: str, tokens: set[str], sym: str, doc: str) -> float:
    blob = _normalize(f"{sym} {doc.split(chr(10), 1)[0]}")
    seq = difflib.SequenceMatcher(None, query, blob).ratio()
    overlap = len(tokens & set(_normalize(sym).split())) / max(len(tokens), 1)
    substr = 0.0
    compact = query.replace(" ", "")
    if sym in compact or sym in query:
        substr = 0.45
    for tok in tokens:
        if tok == sym or (len(tok) > 2 and (tok in sym or sym in tok)):
            substr = max(substr, 0.5)
        alias = _ALIASES.get(tok)
        if alias == sym:
            substr = max(substr, 0.7)
    return max(seq, overlap + substr, substr)


def suggest_markers(
    query: str,
    level: str,
    *,
    n: int = 8,
    cutoff: float = 0.3,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Closest Haystack symbols for a node name / freeform query at a tree level."""
    q = _normalize(query)
    if not q:
        return []
    catalog = catalog_for_level(level, path=path)
    index = load_defs_index(path)
    tokens = set(q.split()) | {_ALIASES.get(t, t) for t in q.split()}

    scored: list[tuple[float, str]] = []
    for sym, doc in catalog.items():
        score = _score_symbol(q, tokens, sym, doc)
        if score >= cutoff:
            scored.append((score, sym))

    scored.sort(key=lambda item: (-item[0], item[1]))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for score, sym in scored:
        if sym in seen:
            continue
        seen.add(sym)
        out.append(
            {
                "symbol": sym,
                "doc": catalog.get(sym) or index.get(sym, {}).get("doc", ""),
                "score": round(score, 4),
            }
        )
        if len(out) >= n:
            break
    return out


def guess_marker_bundle(
    query: str,
    level: str = "point",
    *,
    path: str | None = None,
    role_cutoff: float = 0.35,
) -> dict[str, Any]:
    """One-shot FinStack/Niagara-style tag set: best fuzzy pick per role, applied together."""
    q = _normalize(query)
    level_key = "equip" if level == "equipment" else level
    catalog = catalog_for_level(level_key if level_key in LEVEL_MARKERS else "point", path=path)
    index = load_defs_index(path)
    tokens = set(q.split()) | {_ALIASES.get(t, t) for t in q.split()}

    roles = POINT_ROLES if level_key == "point" else {
        "entity": ("equip", "ahu", "vav", "fan", "pump", "boiler", "chiller"),
        "device": ("damper", "coil", "filter", "motor"),
    }

    by_role: dict[str, dict[str, Any] | None] = {}
    markers: list[str] = []

    for role, candidates in roles.items():
        best: tuple[float, str] | None = None
        for sym in candidates:
            if sym not in catalog and sym not in index:
                continue
            # Always keep entity/history seeds when present in catalog.
            forced = role in {"entity", "history"} and sym in {"point", "his", "equip"}
            doc = catalog.get(sym) or index.get(sym, {}).get("doc", "")
            score = _score_symbol(q, tokens, sym, doc)
            if forced:
                score = max(score, 0.99 if sym == "point" and level_key == "point" else 0.9)
            if score < role_cutoff and not forced:
                continue
            if best is None or score > best[0]:
                best = (score, sym)
        if best is None:
            by_role[role] = None
            continue
        score, sym = best
        by_role[role] = {
            "symbol": sym,
            "doc": catalog.get(sym) or index.get(sym, {}).get("doc", ""),
            "score": round(score, 4),
        }
        if sym not in markers:
            markers.append(sym)

    # Ensure historized points always carry point+his when guessing points.
    if level_key == "point":
        for required in ("point", "his"):
            if (required in catalog or required in index) and required not in markers:
                markers.insert(0 if required == "point" else len(markers), required)
        # FinStack-style default: measured quantities without cmd/sp tokens → sensor.
        if (
            by_role.get("function") is None
            and by_role.get("quantity") is not None
            and ("sensor" in catalog or "sensor" in index)
        ):
            by_role["function"] = {
                "symbol": "sensor",
                "doc": catalog.get("sensor") or index.get("sensor", {}).get("doc", ""),
                "score": 0.5,
            }
            if "sensor" not in markers:
                markers.append("sensor")

    return {
        "query": query,
        "level": level_key,
        "markers": markers,
        "by_role": by_role,
    }
