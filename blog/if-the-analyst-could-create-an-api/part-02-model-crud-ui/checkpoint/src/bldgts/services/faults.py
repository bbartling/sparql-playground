"""Open-FDD fault applicability over Haystack markers + ofddRole tags."""

from __future__ import annotations

from dataclasses import dataclass

from bldgts.graph.namespaces import BLDG, BTS
from bldgts.haystack.metadata import markers_of, metadata
from bldgts.services.points import validate_equipment_id
from open_fdd.rules import RULES
from rdflib import Graph, URIRef

# Role → required ofddRole tag value (from points CSV), optional owner markers.
ROLE_REQUIREMENTS: dict[str, tuple[str, frozenset[str] | None]] = {
    "duct-static-pressure": ("duct-static-pressure", None),
    "duct-static-pressure-sp": ("duct-static-pressure-sp", None),
    "fan-cmd": ("fan-cmd", frozenset({"fan"})),
    "fan-status": ("fan-status", frozenset({"fan"})),
    "return-fan-cmd": ("return-fan-cmd", frozenset({"fan"})),
    "discharge-air-temp": ("discharge-air-temp", None),
    "discharge-air-temp-sp": ("discharge-air-temp-sp", None),
    "mixed-air-temp": ("mixed-air-temp", None),
    "return-air-temp": ("return-air-temp", None),
    "outside-air-temp": ("outside-air-temp", None),
    "outside-air-damper": ("outside-air-damper", frozenset({"damper"})),
    "cooling-valve": ("cooling-valve", frozenset({"valve"})),
    "heating-valve": ("heating-valve", frozenset({"valve"})),
    "occupied": ("occupied", None),
    "web-outside-air-temp": ("web-outside-air-temp", None),
}


@dataclass
class FaultRow:
    rule_id: str
    title: str
    applicable: bool
    generic: bool
    reason: str


def equipment_kind(union: Graph, equipment_id: str) -> str | None:
    equip = BLDG[equipment_id]
    marks = markers_of(union, equip)
    if "ahu" in marks:
        return "ahu"
    return None


def _equip_subtree(g: Graph, equipment_id: str) -> set[URIRef]:
    """AHU plus nested equip parts that equipRef (transitively) to it."""
    root = BLDG[equipment_id]
    out = {root}
    changed = True
    while changed:
        changed = False
        for entity in list(g.subjects(BTS.hasHaystackMarker, None)):
            if not isinstance(entity, URIRef) or entity in out:
                continue
            ref = metadata(g, entity).get("equipRef", {})
            if ref.get("kind") != "Ref":
                continue
            raw = str(ref["value"])
            parent = URIRef(raw) if ":" in raw else BLDG[raw]
            if parent in out:
                out.add(entity)
                changed = True
    return out


def _role_satisfied(
    union: Graph, equipment_id: str, role: str, cache: dict[tuple[str, str], bool]
) -> tuple[bool, str]:
    key = (equipment_id, role)
    if key in cache:
        return cache[key], ""
    req = ROLE_REQUIREMENTS.get(role)
    if req is None:
        cache[key] = False
        return False, "no Haystack/ofddRole mapping for role"
    role_tag, owner_markers = req
    subtree = _equip_subtree(union, equipment_id)
    for point in union.subjects(BTS.hasHaystackMarker, None):
        if not isinstance(point, URIRef):
            continue
        if "point" not in markers_of(union, point):
            continue
        meta = metadata(union, point)
        if meta.get("ofddRole", {}).get("value") != role_tag:
            continue
        equip_ref = meta.get("equipRef", {})
        if equip_ref.get("kind") != "Ref":
            continue
        raw = str(equip_ref["value"])
        owner = URIRef(raw) if ":" in raw else BLDG[raw]
        if owner not in subtree:
            continue
        if owner_markers and not owner_markers.issubset(markers_of(union, owner)):
            continue
        cache[key] = True
        return True, ""
    cache[key] = False
    return False, f"missing role {role}"


def list_faults(
    union: Graph,
    equipment_id: str,
    *,
    include_generic: bool = True,
) -> list[FaultRow]:
    validate_equipment_id(equipment_id)
    kind = equipment_kind(union, equipment_id)
    cache: dict[tuple[str, str], bool] = {}
    rows: list[FaultRow] = []
    for rule in RULES:
        roles = list(getattr(rule, "required_roles", []) or [])
        kinds = list(getattr(rule, "equipment_kinds", []) or [])
        generic = not roles
        if generic and not include_generic:
            continue
        if kinds and kind not in kinds:
            rows.append(
                FaultRow(
                    rule_id=rule.id,
                    title=rule.title,
                    applicable=False,
                    generic=generic,
                    reason="equipment kind mismatch",
                )
            )
            continue
        missing = []
        ok = True
        for role in roles:
            satisfied, reason = _role_satisfied(union, equipment_id, role, cache)
            if not satisfied:
                ok = False
                missing.append(reason or role)
        rows.append(
            FaultRow(
                rule_id=rule.id,
                title=rule.title,
                applicable=ok,
                generic=generic,
                reason="" if ok else "; ".join(missing),
            )
        )
    return rows
