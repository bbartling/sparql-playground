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
    "substance": ("air", "water", "steam", "elec", "hot", "chilled", "cool", "heat"),
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
    "state": ("status", "alarm", "enable", "run"),
    "history": ("his",),
}

# Single-token BMS aliases → one Haystack symbol.
_ALIASES: dict[str, str] = {
    "temperature": "temp",
    "temperatures": "temp",
    "tmp": "temp",
    "temp": "temp",
    "static": "pressure",
    "press": "pressure",
    "dp": "pressure",
    "setpoint": "sp",
    "setpoints": "sp",
    "set": "sp",
    "setpt": "sp",
    "spt": "sp",
    "command": "cmd",
    "commands": "cmd",
    "cmd": "cmd",
    "output": "cmd",
    "out": "cmd",
    "ao": "cmd",
    "bo": "cmd",
    "do": "cmd",
    "input": "sensor",
    "ai": "sensor",
    "bi": "sensor",
    "di": "sensor",
    "sa": "discharge",
    "da": "discharge",
    "supply": "discharge",
    "sup": "discharge",
    "rat": "return",
    "ra": "return",
    "ret": "return",
    "return": "return",
    "oa": "outside",
    "oat": "outside",
    "mat": "mixed",
    "ea": "exhaust",
    "exh": "exhaust",
    "sat": "discharge",
    "dat": "discharge",
    "vfd": "speed",
    "spd": "speed",
    "speed": "speed",
    "damper": "damper",
    "dmp": "damper",
    "vlv": "valve",
    "valve": "valve",
    "fan": "fan",
    "fans": "fan",
    "pump": "pump",
    "pumps": "pump",
    "coil": "coil",
    "filter": "filter",
    "filt": "filter",
    "humidity": "humidity",
    "rh": "humidity",
    "humid": "humidity",
    "flow": "flow",
    "cfm": "flow",
    "gpm": "flow",
    "pressure": "pressure",
    "pressurization": "pressure",
    "zone": "zone",
    "zn": "zone",
    "duct": "duct",
    "air": "air",
    "water": "water",
    "steam": "steam",
    "elec": "elec",
    "electrical": "elec",
    "power": "power",
    "kw": "power",
    "energy": "energy",
    "kwh": "energy",
    "occupancy": "occupancy",
    "occ": "occupancy",
    "co2": "co2",
    "enable": "enable",
    "en": "enable",
    "run": "run",
    "status": "status",
    "sts": "status",
    "alarm": "alarm",
    "alm": "alarm",
    "position": "position",
    "pos": "position",
    "heat": "heat",
    "htg": "heat",
    "cool": "cool",
    "clg": "cool",
    "chilled": "chilled",
    "hot": "hot",
    "mixed": "mixed",
    "outside": "outside",
    "outdoor": "outside",
    "exhaust": "exhaust",
    "discharge": "discharge",
    "leaving": "leaving",
    "entering": "entering",
    "sensor": "sensor",
    "sp": "sp",
    "point": "point",
    "his": "his",
}

# Compound BMS abbreviations (after lower/strip) → several Haystack symbols.
# Matched as whole tokens after first-pass tokenization.
_COMPOUND: dict[str, tuple[str, ...]] = {
    # Fans / commands
    "rfc": ("return", "fan", "cmd"),
    "rfs": ("return", "fan", "status"),
    "rf": ("return", "fan"),
    "sfc": ("discharge", "fan", "cmd"),
    "sfs": ("discharge", "fan", "status"),
    "sf": ("discharge", "fan"),
    "efc": ("exhaust", "fan", "cmd"),
    "efs": ("exhaust", "fan", "status"),
    "ef": ("exhaust", "fan"),
    "sfan": ("discharge", "fan"),
    "rfan": ("return", "fan"),
    "efan": ("exhaust", "fan"),
    "sfancmd": ("discharge", "fan", "cmd"),
    "rfancmd": ("return", "fan", "cmd"),
    "efancmd": ("exhaust", "fan", "cmd"),
    "supplyfancmd": ("discharge", "fan", "cmd"),
    "returnfancmd": ("return", "fan", "cmd"),
    "exhaustfancmd": ("exhaust", "fan", "cmd"),
    "returnfancommand": ("return", "fan", "cmd"),
    "supplyfancommand": ("discharge", "fan", "cmd"),
    "exhaustfancommand": ("exhaust", "fan", "cmd"),
    "returnfan": ("return", "fan"),
    "supplyfan": ("discharge", "fan"),
    "exhaustfan": ("exhaust", "fan"),
    # Temps
    "sat": ("discharge", "air", "temp"),
    "dat": ("discharge", "air", "temp"),
    "rat": ("return", "air", "temp"),
    "oat": ("outside", "air", "temp"),
    "mat": ("mixed", "air", "temp"),
    "zat": ("zone", "air", "temp"),
    "znt": ("zone", "temp"),
    "satsp": ("discharge", "air", "temp", "sp"),
    "datsp": ("discharge", "air", "temp", "sp"),
    "ratsp": ("return", "air", "temp", "sp"),
    "zatsp": ("zone", "air", "temp", "sp"),
    "sas": ("discharge", "air", "temp"),
    "ras": ("return", "air", "temp"),
    # Static / duct pressure
    "sasp": ("discharge", "air", "pressure", "sp"),
    "ductstatic": ("duct", "pressure"),
    "ductstaticsp": ("duct", "pressure", "sp"),
    "dsp": ("duct", "pressure"),
    "dsps": ("duct", "pressure", "sp"),
    "sa_static": ("discharge", "air", "pressure"),
    "sastatic": ("discharge", "air", "pressure"),
    "sastaticsp": ("discharge", "air", "pressure", "sp"),
    # Dampers / valves
    "oad": ("outside", "air", "damper"),
    "oadp": ("outside", "air", "damper", "position"),
    "oadcmd": ("outside", "air", "damper", "cmd"),
    "mad": ("mixed", "air", "damper"),
    "rad": ("return", "air", "damper"),
    "ccv": ("cool", "coil", "valve"),
    "hcv": ("heat", "coil", "valve"),
    # Humidity / CO2 / occ
    "sah": ("discharge", "air", "humidity"),
    "rah": ("return", "air", "humidity"),
    "znh": ("zone", "humidity"),
    "znco2": ("zone", "co2"),
    "zco2": ("zone", "co2"),
    "znocc": ("zone", "occupancy"),
    # VFD / speed
    "sfvfd": ("discharge", "fan", "speed"),
    "rfvfd": ("return", "fan", "speed"),
    "sfspd": ("discharge", "fan", "speed"),
    "rfspd": ("return", "fan", "speed"),
    "fanspeed": ("fan", "speed"),
    "fanspd": ("fan", "speed"),
    # Water loops
    "chw": ("chilled", "water"),
    "chwv": ("chilled", "water", "valve"),
    "chwvalve": ("chilled", "water", "valve"),
    "hw": ("hot", "water"),
    "hwv": ("hot", "water", "valve"),
    "hwvalve": ("hot", "water", "valve"),
    "chilledwatervalve": ("chilled", "water", "valve"),
    "hotwatervalve": ("hot", "water", "valve"),
    # Equipment phrases
    "airhandler": ("ahu",),
    "airhandling": ("ahu",),
    "airhandlingunit": ("ahu",),
    "airhandlerunit": ("ahu",),
}


def _normalize(text: str) -> str:
    return " ".join(_TOKEN.findall(text.lower()))


def _expand_tokens(text: str) -> set[str]:
    """Tokenize a BMS / Haystack-ish name into Haystack-oriented tokens."""
    raw = _normalize(text)
    if not raw:
        return set()
    # Also try glued forms: "AHU RF-C" → tokens ahu rf c, plus compound "rfc" from rf+c.
    parts = raw.split()
    glued_pairs = ["".join(parts[i : i + 2]) for i in range(len(parts) - 1)]
    glued_triples = ["".join(parts[i : i + 3]) for i in range(len(parts) - 2)]
    candidates = set(parts) | set(glued_pairs) | set(glued_triples) | {"".join(parts)}

    out: set[str] = set()
    for tok in candidates:
        if tok in _COMPOUND:
            out.update(_COMPOUND[tok])
            continue
        alias = _ALIASES.get(tok)
        if alias:
            out.add(alias)
        # Keep original short tokens that are already Haystack symbols.
        if (
            tok in _ALIASES.values()
            or tok
            in {
                "point",
                "his",
                "sensor",
                "sp",
                "cmd",
                "fan",
                "ahu",
                "vav",
            }
            or len(tok) > 2
        ):
            out.add(tok)
    # Always keep individual parts for scoring overlap.
    for tok in parts:
        alias = _ALIASES.get(tok, tok)
        out.add(alias)
        if tok in _COMPOUND:
            out.update(_COMPOUND[tok])
    return out


def _score_symbol(query: str, tokens: set[str], sym: str, doc: str) -> float:
    blob = _normalize(f"{sym} {doc.split(chr(10), 1)[0]}")
    seq = difflib.SequenceMatcher(None, query, blob).ratio()
    overlap = len(tokens & set(_normalize(sym).split())) / max(len(tokens), 1)
    substr = 0.0
    compact = query.replace(" ", "")
    if sym in compact or sym in query:
        substr = 0.45
    if sym in tokens:
        substr = max(substr, 0.85)
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
    tokens = _expand_tokens(query)

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
    tokens = _expand_tokens(query)

    roles = (
        POINT_ROLES
        if level_key == "point"
        else {
            "entity": ("equip", "ahu", "vav", "fan", "pump", "boiler", "chiller"),
            "device": ("damper", "coil", "filter", "motor"),
        }
    )

    by_role: dict[str, dict[str, Any] | None] = {}
    markers: list[str] = []

    for role, candidates in roles.items():
        best: tuple[float, str] | None = None
        for sym in candidates:
            if sym not in catalog and sym not in index:
                continue
            # Always keep entity/history seeds when present in catalog.
            forced = role in {"entity", "history"} and sym in {"point", "his", "equip"}
            # Strong prior when compound/alias expansion already produced this symbol.
            prior = 0.95 if sym in tokens and not forced else 0.0
            doc = catalog.get(sym) or index.get(sym, {}).get("doc", "")
            score = max(_score_symbol(q, tokens, sym, doc), prior)
            if forced:
                score = max(score, 0.99 if sym == "point" and level_key == "point" else 0.9)
            # Quantity/device/state need a real token hit — avoid "valve"≈"voltage" noise.
            if role in {"quantity", "device", "state", "substance"} and sym not in tokens:
                continue
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

    # Include strong compound/alias expansions that roles may have skipped.
    role_symbols = {sym for cands in roles.values() for sym in cands}
    for sym in sorted(tokens):
        if sym in markers or sym not in role_symbols:
            continue
        if sym in catalog or sym in index:
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
        # Command/status without quantity still needs a function marker when device tokens hit.
        if by_role.get("function") is None and "cmd" in tokens:
            by_role["function"] = {
                "symbol": "cmd",
                "doc": catalog.get("cmd") or index.get("cmd", {}).get("doc", ""),
                "score": 0.9,
            }
            if "cmd" not in markers:
                markers.append("cmd")

        # Air-side sections almost always imply substance=air for HVAC points.
        air_sections = {"return", "discharge", "outside", "mixed", "exhaust", "zone"}
        air_companions = {
            "temp",
            "humidity",
            "damper",
            "fan",
            "pressure",
            "flow",
            "co2",
            "occupancy",
        }
        have = set(markers)
        if (
            have & air_sections
            and have & air_companions
            and "air" not in have
            and ("air" in catalog or "air" in index)
        ):
            markers.append("air")

    return {
        "query": query,
        "level": level_key,
        "markers": markers,
        "by_role": by_role,
        "tokens": sorted(tokens),
    }
