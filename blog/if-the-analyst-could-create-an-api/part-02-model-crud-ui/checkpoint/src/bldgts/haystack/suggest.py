from __future__ import annotations

import difflib
import re
from typing import Any

from bldgts.haystack.defs import catalog_for_level, is_subtype

_TOKEN = re.compile(r"[a-z0-9]+", re.I)

# Roles organize review; they are not mutually exclusive ontology dimensions.
# Multiple qualifiers (e.g. chilled + water, discharge + duct) must survive.
POINT_ROLES: dict[str, tuple[str, ...]] = {
    "entity": ("point",),
    "function": ("sensor", "sp", "cmd", "synthetic", "computed", "ml", "sim"),
    "substance": ("air", "water", "steam", "elec", "co2"),
    "qualifier": ("hot", "chilled", "cool", "heat", "delta", "effective"),
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
        "occupancy",
        "power",
        "energy",
        "volt",
        "current",
        "speed",
        "position",
        "concentration",
        "level",
        "freq",
        "enthalpy",
    ),
    "device": ("damper", "valve", "fan", "coil", "filter", "pump", "motor"),
    "state": ("alarm", "enable", "run"),
    "capability": ("his", "cur", "writable", "hisTotalized"),
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
    "setpt": "sp",
    "spt": "sp",
    "command": "cmd",
    "commands": "cmd",
    "cmd": "cmd",
    "output": "cmd",
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
    "status": "sensor",
    "sts": "sensor",
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
    "history": "his",
    "historized": "his",
    "trended": "his",
    "cur": "cur",
    "realtime": "cur",
    "writable": "writable",
    "synthetic": "synthetic",
    "computed": "computed",
    "calculated": "computed",
    "simulation": "sim",
    "simulated": "sim",
    "ml": "ml",
    "sim": "sim",
    "differential": "delta",
    "delta": "delta",
    "voltage": "volt",
    "current": "current",
    "concentration": "concentration",
    "level": "level",
    "frequency": "freq",
    "enthalpy": "enthalpy",
}

# Compound BMS abbreviations (after lower/strip) → several Haystack symbols.
# Matched as whole tokens after first-pass tokenization.
_COMPOUND: dict[str, tuple[str, ...]] = {
    # Status is observed input; fan/pump/motor run state is resolved below.
    "status": ("sensor",),
    "sts": ("sensor",),
    "sa": ("discharge", "air"),
    "da": ("discharge", "air"),
    "ra": ("return", "air"),
    "oa": ("outside", "air"),
    "ea": ("exhaust", "air"),
    # Fans / commands
    "rfc": ("return", "fan", "cmd"),
    "rfs": ("return", "fan", "run", "sensor"),
    "rf": ("return", "fan"),
    "sfc": ("discharge", "fan", "cmd"),
    "sfs": ("discharge", "fan", "run", "sensor"),
    "sf": ("discharge", "fan"),
    "efc": ("exhaust", "fan", "cmd"),
    "efs": ("exhaust", "fan", "run", "sensor"),
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
    "sas": ("discharge", "air"),
    "ras": ("return", "air"),
    # Static / duct pressure
    "sasp": ("discharge", "air", "sp"),
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
    "chilledwater": ("chilled", "water"),
    "hotwater": ("hot", "water"),
    "coolingtower": ("coolingTower",),
    "machinelearning": ("ml",),
    # Equipment phrases
    "airhandler": ("ahu",),
    "airhandling": ("ahu",),
    "airhandlingunit": ("ahu",),
    "airhandlerunit": ("ahu",),
}


def _normalize(text: str) -> str:
    # Camel case is common in BAS exports; retain whole-token matches, never substrings
    # from opaque point IDs (e.g. 'space42' must not imply sp).
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return " ".join(_TOKEN.findall(text.lower()))


def _token_evidence(
    text: str,
    catalog: dict[str, str] | None = None,
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    parts = _normalize(text).split()
    candidates = set(parts)
    for size in (2, 3, 4):
        candidates.update("".join(parts[i : i + size]) for i in range(len(parts) - size + 1))
    canonical = {_normalize(sym).replace(" ", ""): sym for sym in (catalog or {})}
    evidence: dict[str, dict[str, Any]] = {}
    for token in sorted(candidates):
        symbols = _COMPOUND.get(token)
        source = "abbreviation"
        if symbols is None and token in _ALIASES:
            symbols = (_ALIASES[token],)
            source = "token" if symbols[0] == token else "alias"
        if symbols is None and token in canonical:
            symbols = (canonical[token],)
            source = "token"
        if symbols is None:
            # Exact tag names such as ahu, vav, coolingTower also qualify.
            symbols = (token,) if token in parts else ()
            source = "token"
        for symbol in symbols:
            hit = evidence.setdefault(symbol, {"source": source, "matches": [], "score": 0.95})
            hit["matches"].append(token)
    return set(parts) | set(evidence), evidence


def _expand_tokens(text: str) -> set[str]:
    return _token_evidence(text)[0]


def _score_symbol(query: str, tokens: set[str], sym: str, doc: str) -> float:
    """Rank search results without promoting short substrings to exact matches."""
    normalized_sym = _normalize(sym)
    if sym in tokens or normalized_sym in tokens:
        return 0.98
    parts = query.split()
    # Docs only contribute whole word overlap; long prose similarity produces noise.
    doc_words = set(_normalize(doc.split(chr(10), 1)[0]).split())
    overlap = len(set(parts) & doc_words) / max(len(set(parts)), 1)
    best = max(
        (
            difflib.SequenceMatcher(None, token, normalized_sym).ratio()
            for token in parts
            if len(token) >= 4 and len(normalized_sym) >= 4
        ),
        default=0.0,
    )
    return max(best * 0.75, overlap * 0.4)


def suggest_markers(
    query: str,
    level: str,
    *,
    n: int = 8,
    cutoff: float = 0.3,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Search the real marker catalog. Fuzzy results require a human selection."""
    q = _normalize(query)
    if not q or n <= 0:
        return []
    catalog = catalog_for_level(level, path=path)
    tokens = _token_evidence(query, catalog)[0]
    scored = [(_score_symbol(q, tokens, sym, doc), sym) for sym, doc in catalog.items()]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"symbol": sym, "doc": catalog[sym], "score": round(score, 4)}
        for score, sym in scored
        if score >= cutoff
    ][:n]


def guess_marker_bundle(
    query: str,
    level: str = "point",
    *,
    path: str | None = None,
    role_cutoff: float = 0.35,
) -> dict[str, Any]:
    """Conservative proposal from explicit BAS tokens, with evidence for review.

    Entity type comes from the selected tree level. Function, live/history/write
    capability and scalar metadata cannot be established from a vague point name.
    Fuzzy search is exposed separately rather than silently applying near matches.
    """
    level_key = level.strip().lower()
    level_key = "equip" if level_key == "equipment" else level_key
    catalog = catalog_for_level(level_key, path=path)
    tokens, evidence = _token_evidence(query, catalog)
    warnings: list[str] = []
    seeds = {
        "point": ("point",),
        "equip": ("equip",),
        "part": ("equip",),
        "site": ("site",),
        "building": ("site",),
        "floor": ("space", "floor"),
        "space": ("space",),
    }[level_key]
    selected = {sym for sym in evidence if sym in catalog and role_cutoff <= evidence[sym]["score"]}
    for sym in seeds:
        if sym in catalog:
            selected.add(sym)
            evidence[sym] = {"source": "tree-level", "matches": [level_key], "score": 1.0}

    if level_key == "point":
        if any({"sas", "ras", "sasp"}.intersection(hit["matches"]) for hit in evidence.values()):
            warnings.append(
                "SAS/RAS/SA-SP abbreviations are ambiguous; confirm the measured quantity."
            )
        if (
            {"status", "sts"}.intersection(tokens)
            and {"fan", "pump", "motor"}.intersection(selected)
            and "run" in catalog
        ):
            selected.add("run")
            evidence["run"] = {
                "source": "equipment-status",
                "matches": ["status"],
                "score": 0.95,
            }
        if "position" in tokens:
            warnings.append(
                "Position is BAS context, not a standard marker; confirm whether this is "
                "sensor feedback, cmd output, or an sp limit."
            )
        functions = {sym for sym in selected if is_subtype(sym, "pointFunction", path=path)}
        # A synthetic subtype refines synthetic; it is not a conflicting second function.
        leaves = {
            sym
            for sym in functions
            if not any(sym != other and is_subtype(other, sym, path=path) for other in functions)
        }
        if len(leaves) > 1:
            selected.difference_update(functions)
            warnings.append(
                "Conflicting point functions in the name: "
                + ", ".join(sorted(leaves))
                + ". Choose the actual function before applying."
            )
        elif leaves:
            selected.difference_update(functions - leaves)
            # synthetic is mandatory on computed/ml/sim records.
            if "synthetic" in catalog and any(
                is_subtype(sym, "synthetic", path=path) for sym in leaves
            ):
                selected.add("synthetic")
                evidence["synthetic"] = {
                    "source": "synthetic-subtype",
                    "matches": sorted(leaves),
                    "score": 0.95,
                }
        else:
            warnings.append("Point function is ambiguous; choose sensor, cmd, sp, or synthetic.")
        if not selected.intersection({"his", "cur", "writable"}):
            warnings.append("Confirm actual his, cur, and writable capabilities from the source.")
        warnings.append(
            "Confirm kind, units, references, and any history metadata from the source."
        )

    ordered = [sym for sym in seeds if sym in selected]
    ordered.extend(sorted(selected - set(ordered)))
    roles = POINT_ROLES if level_key == "point" else {"entity": tuple(ordered)}
    by_role: dict[str, dict[str, Any] | None] = {}
    for role, candidates in roles.items():
        matches = [sym for sym in ordered if sym in candidates]
        by_role[role] = (
            {
                "symbol": matches[0],
                "symbols": matches,
                "doc": catalog[matches[0]],
                "score": evidence[matches[0]]["score"],
            }
            if matches
            else None
        )
    # Keep the historical field name for clients that display its role summary.
    if level_key == "point":
        by_role["history"] = by_role["capability"]
    return {
        "query": query,
        "level": level_key,
        "markers": ordered,
        "by_role": by_role,
        "tokens": sorted(tokens),
        "evidence": {sym: evidence[sym] for sym in ordered},
        "warnings": warnings,
        "confidence": "review-required",
        "needs_review": True,
    }
