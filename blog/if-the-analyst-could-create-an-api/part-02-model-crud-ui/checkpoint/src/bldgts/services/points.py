"""Point and equipment discovery over Haystack markers + opaque timeseries refs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bldgts.graph.namespaces import BLDG, BTS, RDF, REF
from bldgts.haystack.metadata import markers_of, metadata
from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
CLASS_RE = re.compile(r"^[A-Z][A-Za-z0-9_]{0,127}$")
TAG_RE = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass
class PointSummary:
    point_id: str
    label: str
    brick_class: str  # retained field name for API compat; holds ofddRole or markers
    owner_id: str
    timeseries_id: str | None
    unit: str | None


def _local_name(uri: URIRef) -> str:
    s = str(uri)
    if "#" in s:
        return s.rsplit("#", 1)[-1]
    return s.rsplit("/", 1)[-1]


def validate_equipment_id(equipment_id: str) -> None:
    if not ID_RE.match(equipment_id):
        raise ValueError("invalid equipment id")


def validate_class_name(name: str) -> None:
    if not CLASS_RE.match(name):
        raise ValueError("invalid class name")


def validate_tags(tags: list[str]) -> None:
    if len(tags) > 20:
        raise ValueError("too many tags")
    for t in tags:
        if not TAG_RE.match(t):
            raise ValueError("invalid tag")


def is_point_subclass(union: Graph, class_name: str) -> bool:
    """Compatibility stub: class filter now matches ofddRole or marker sets."""
    del union, class_name
    return True


def list_equipment(union: Graph) -> list[dict]:
    out = []
    for equip in sorted(union.subjects(BTS.hasHaystackMarker, None), key=str):
        if not isinstance(equip, URIRef) or not str(equip).startswith(str(BLDG)):
            continue
        marks = markers_of(union, equip)
        if "equip" not in marks or "ahu" not in marks:
            continue
        eid = _local_name(equip)
        label = next(union.objects(equip, RDFS.label), eid)
        out.append({"equipment_id": eid, "label": str(label) if label else eid})
    return out


def _equipment_uri(equipment_id: str) -> URIRef:
    return BLDG[equipment_id]


def _equip_subtree(g: Graph, equipment: URIRef) -> set[URIRef]:
    out = {equipment}
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


def _point_in_scope(g: Graph, point: URIRef, equipment: URIRef) -> bool:
    meta = metadata(g, point)
    ref = meta.get("equipRef", {})
    if ref.get("kind") != "Ref":
        return False
    raw = str(ref["value"])
    owner = URIRef(raw) if ":" in raw else BLDG[raw]
    return owner in _equip_subtree(g, equipment)


def find_points(
    union: Graph,
    equipment_id: str,
    *,
    brick_class: str | None = None,
    tags: list[str] | None = None,
    parent_class: str | None = None,
    include_subclasses: bool = True,
    include_fed_zones: bool = False,
) -> list[PointSummary]:
    del include_subclasses, include_fed_zones
    validate_equipment_id(equipment_id)
    equipment = _equipment_uri(equipment_id)
    if tags:
        validate_tags(tags)

    results: list[PointSummary] = []
    for p in union.subjects(BTS.hasHaystackMarker, None):
        if not isinstance(p, URIRef) or not str(p).startswith(str(BLDG)):
            continue
        if "point" not in markers_of(union, p):
            continue
        if not _point_in_scope(union, p, equipment):
            continue
        meta = metadata(union, p)
        role = str(meta.get("ofddRole", {}).get("value") or "")
        marks = markers_of(union, p)
        if brick_class and role != brick_class and brick_class not in marks:
            continue
        if parent_class:
            owner_raw = meta.get("equipRef", {}).get("value")
            if not owner_raw:
                continue
            owner = URIRef(str(owner_raw)) if ":" in str(owner_raw) else BLDG[str(owner_raw)]
            if parent_class not in markers_of(union, owner):
                continue
        if tags and not set(tags).issubset(marks):
            continue
        pid = _local_name(p)
        label = next(union.objects(p, RDFS.label), pid)
        owner_id = str(meta.get("equipRef", {}).get("value") or "")
        ts_id = None
        for ref in union.objects(p, REF.hasExternalReference):
            ids = list(union.objects(ref, REF.hasTimeseriesId))
            if ids:
                ts_id = str(ids[0])
                break
        unit = meta.get("unit", {}).get("value")
        results.append(
            PointSummary(
                point_id=pid,
                label=str(label),
                brick_class=role or ",".join(sorted(marks)),
                owner_id=owner_id,
                timeseries_id=ts_id,
                unit=str(unit) if unit is not None else None,
            )
        )
    results.sort(key=lambda x: x.point_id)
    return results


def get_point(union: Graph, point_id: str) -> PointSummary | None:
    if not ID_RE.match(point_id):
        return None
    p = BLDG[point_id]
    if (
        "point" not in markers_of(union, p)
        and (p, REF.hasExternalReference, None) not in union
        and (p, RDF.type, None) not in union
    ):
        return None
    meta = metadata(union, p)
    marks = markers_of(union, p)
    role = str(meta.get("ofddRole", {}).get("value") or "")
    label = next(union.objects(p, RDFS.label), point_id)
    owner_id = str(meta.get("equipRef", {}).get("value") or "")
    ts_id = None
    for ref in union.objects(p, REF.hasExternalReference):
        ids = list(union.objects(ref, REF.hasTimeseriesId))
        if ids:
            ts_id = str(ids[0])
            break
    unit = meta.get("unit", {}).get("value")
    return PointSummary(
        point_id=point_id,
        label=str(label),
        brick_class=role or ",".join(sorted(marks)),
        owner_id=owner_id,
        timeseries_id=ts_id,
        unit=str(unit) if unit is not None else None,
    )
