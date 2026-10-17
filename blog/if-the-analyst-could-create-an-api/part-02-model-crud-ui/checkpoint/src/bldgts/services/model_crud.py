"""Haystack-oriented model CRUD over the runtime graph (copy-on-write + snapshot TTL).

Preserves every existing ``ref:TimeseriesReference``. Soft-delete uses ``bts:hidden``.
New points always mint a TimeseriesReference + opaque timeseries id.
UI tags are Project Haystack markers (``bts:hasHaystackMarker``), not shipping ops tags.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from bldgts.graph.namespaces import BLDG, BRICK, BTS, REF
from bldgts.graph.service import ConflictError, GraphService
from bldgts.haystack.defs import catalog_for_level
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# Seed Haystack markers from legacy Brick classes until the seed TTL is fully Haystack.
_BRICK_TO_MARKERS: dict[str, tuple[str, ...]] = {
    "Site": ("site",),
    "Building": ("site",),
    "Floor": ("floor",),
    "Air_Handler_Unit": ("equip", "ahu"),
    "Fan": ("equip", "fan"),
    "Supply_Fan": ("equip", "fan"),
    "Return_Fan": ("equip", "fan"),
    "Variable_Air_Volume_Box": ("equip", "vav"),
    "Sensor": ("point", "sensor"),
    "Setpoint": ("point", "sp"),
    "Command": ("point", "cmd"),
    "Status": ("point", "status"),
    "Point": ("point",),
}

_EQUIP_KINDS = {
    "ahu": BRICK.Air_Handler_Unit,
    "air_handler_unit": BRICK.Air_Handler_Unit,
    "fan": BRICK.Fan,
    "supply_fan": BRICK.Supply_Fan,
    "return_fan": BRICK.Return_Fan,
    "vav": BRICK.Variable_Air_Volume_Box,
    "sensor": BRICK.Sensor,
}

_POINT_KINDS = {
    "point": BRICK.Point,
    "sensor": BRICK.Sensor,
    "setpoint": BRICK.Setpoint,
    "command": BRICK.Command,
    "status": BRICK.Status,
}


def _safe_id(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip())[:128]
    if not cleaned:
        raise ValueError("id must contain alphanumeric characters")
    return cleaned


def _local(iri: URIRef) -> str:
    text = str(iri)
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    return text.rsplit("/", 1)[-1]


def _label(g: Graph, iri: URIRef) -> str:
    for o in g.objects(iri, RDFS.label):
        return str(o)
    return _local(iri)


def _is_hidden(g: Graph, iri: URIRef) -> bool:
    return (iri, BTS.hidden, Literal(True, datatype=XSD.boolean)) in g


def _brick_types(g: Graph, iri: URIRef) -> list[str]:
    out: list[str] = []
    for o in g.objects(iri, RDF.type):
        if str(o).startswith(str(BRICK)):
            out.append(_local(URIRef(o)))
    return out


def _timeseries_id(g: Graph, point: URIRef) -> str | None:
    for ref in g.objects(point, REF.hasExternalReference):
        for tid in g.objects(ref, REF.hasTimeseriesId):
            return str(tid)
    return None


def database_iri(g: Graph) -> URIRef:
    for s, _, _ in g.triples((None, RDF.type, REF.Database)):
        return URIRef(s)
    for s, _, _ in g.triples((None, RDF.type, BRICK.Database)):
        return URIRef(s)
    return BLDG.timeseries_db


def _stored_markers(g: Graph, iri: URIRef) -> list[str]:
    return sorted({str(o) for o in g.objects(iri, BTS.hasHaystackMarker)})


def _seed_markers(g: Graph, iri: URIRef, node_type: str) -> list[str]:
    """Brick-derived hint markers only — not treated as saved Haystack tags."""
    seeded: list[str] = []
    for brick_type in _brick_types(g, iri):
        seeded.extend(_BRICK_TO_MARKERS.get(brick_type, ()))
    if not seeded:
        seeded.extend(
            {
                "site": ("site",),
                "building": ("site",),
                "floor": ("floor",),
                "equip": ("equip",),
                "part": ("equip",),
                "point": ("point",),
            }.get(node_type, ())
        )
    out: list[str] = []
    for marker in seeded:
        if marker not in out:
            out.append(marker)
    return out


def _point_complete(markers: list[str]) -> bool:
    """Historized Haystack point: point + his + a function marker."""
    have = set(markers)
    return "point" in have and "his" in have and bool(have & {"sensor", "sp", "cmd"})


def _coverage_status(*, total: int, complete: int) -> str:
    if total <= 0:
        return "green"
    if complete >= total:
        return "green"
    if complete == 0:
        return "red"
    return "yellow"


def _annotate_coverage(node: dict[str, Any]) -> dict[str, Any]:
    """Roll up point tagging completeness for branch highlighting."""
    if node.get("node_type") == "point":
        done = 1 if node.get("complete") else 0
        node["points_total"] = 1
        node["points_complete"] = done
        node["coverage"] = "green" if done else "red"
        return node
    total = 0
    complete = 0
    kids = []
    for child in node.get("children") or []:
        annotated = _annotate_coverage(child)
        kids.append(annotated)
        total += int(annotated.get("points_total") or 0)
        complete += int(annotated.get("points_complete") or 0)
    node["children"] = kids
    node["points_total"] = total
    node["points_complete"] = complete
    node["coverage"] = _coverage_status(total=total, complete=complete)
    return node


def build_tree(graph: GraphService) -> list[dict[str, Any]]:
    """Site → building → equipment (+ parts) → points tree for the model UI."""
    g = graph.state.model

    def point_node(point: URIRef) -> dict[str, Any]:
        tid = _timeseries_id(g, point)
        markers = _stored_markers(g, point)
        return {
            "id": _local(point),
            "iri": str(point),
            "name": _label(g, point),
            "node_type": "point",
            "brick_types": _brick_types(g, point),
            "markers": markers,
            "hints": _seed_markers(g, point, "point"),
            "tagged": bool(markers),
            "complete": _point_complete(markers),
            "tags": {k: v for k, v in {"timeseries_id": tid}.items() if v},
            "children": [],
        }

    def points_of(owner: URIRef) -> list[dict[str, Any]]:
        pts: list[dict[str, Any]] = []
        for point in g.objects(owner, BRICK.hasPoint):
            p = URIRef(point)
            if _is_hidden(g, p):
                continue
            pts.append(point_node(p))
        for point, _, _ in g.triples((None, BRICK.isPointOf, owner)):
            p = URIRef(point)
            if _is_hidden(g, p):
                continue
            if not any(child["iri"] == str(p) for child in pts):
                pts.append(point_node(p))
        pts.sort(key=lambda n: n["name"].lower())
        return pts

    def part_nodes(equip: URIRef) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        for part in g.objects(equip, BRICK.hasPart):
            p = URIRef(part)
            if _is_hidden(g, p):
                continue
            # Skip nested buildings/floors here; those hang off site/building.
            types = set(_brick_types(g, p))
            if types & {"Building", "Floor", "Site"}:
                continue
            parts.append(
                {
                    "id": _local(p),
                    "iri": str(p),
                    "name": _label(g, p),
                    "node_type": "part",
                    "brick_types": _brick_types(g, p),
                    "markers": _stored_markers(g, p) or _seed_markers(g, p, "part"),
                    "tags": {},
                    "children": points_of(p),
                }
            )
        parts.sort(key=lambda n: n["name"].lower())
        return parts

    def equip_nodes(building: URIRef | None) -> list[dict[str, Any]]:
        equips: list[dict[str, Any]] = []
        seen: set[str] = set()
        candidates: list[URIRef] = []
        if building is not None:
            for e in g.objects(building, BRICK.hasPart):
                candidates.append(URIRef(e))
            for e, _, _ in g.triples((None, BRICK.isLocatedIn, building)):
                candidates.append(URIRef(e))
        else:
            for e, _, t in g.triples((None, RDF.type, None)):
                if str(t).startswith(str(BRICK)) and _local(URIRef(t)) in {
                    "Air_Handler_Unit",
                    "Variable_Air_Volume_Box",
                    "Chiller",
                    "Boiler",
                }:
                    candidates.append(URIRef(e))

        for e in candidates:
            if _is_hidden(g, e) or str(e) in seen:
                continue
            types = set(_brick_types(g, e))
            if types & {"Floor", "Building", "Site"}:
                continue
            # Prefer top-level equipment (AHU etc.), not tiny parts listed via hasPart.
            top = types & {
                "Air_Handler_Unit",
                "Variable_Air_Volume_Box",
                "Chiller",
                "Boiler",
                "Fan",
                "Pump",
            }
            has_pts = list(g.objects(e, BRICK.hasPoint)) or list(g.subjects(BRICK.isPointOf, e))
            if not top and not has_pts:
                continue
            seen.add(str(e))
            children = part_nodes(e) + points_of(e)
            equips.append(
                {
                    "id": _local(e),
                    "iri": str(e),
                    "name": _label(g, e),
                    "node_type": "equipment",
                    "brick_types": _brick_types(g, e),
                    "markers": _stored_markers(g, e) or _seed_markers(g, e, "equip"),
                    "tags": {},
                    "children": children,
                }
            )
        equips.sort(key=lambda n: n["name"].lower())
        return equips

    roots: list[dict[str, Any]] = []
    sites = [URIRef(s) for s, _, _ in g.triples((None, RDF.type, BRICK.Site))]
    if not sites:
        return [_annotate_coverage(n) for n in equip_nodes(None)]

    for site in sites:
        if _is_hidden(g, site):
            continue
        buildings: list[dict[str, Any]] = []
        for b in g.objects(site, BRICK.hasPart):
            building = URIRef(b)
            if _is_hidden(g, building):
                continue
            if "Building" not in _brick_types(g, building) and not list(
                g.triples((building, RDF.type, BRICK.Building))
            ):
                continue
            buildings.append(
                {
                    "id": _local(building),
                    "iri": str(building),
                    "name": _label(g, building),
                    "node_type": "building",
                    "brick_types": _brick_types(g, building),
                    "markers": _stored_markers(g, building)
                    or _seed_markers(g, building, "building"),
                    "tags": {},
                    "children": equip_nodes(building),
                }
            )
        roots.append(
            {
                "id": _local(site),
                "iri": str(site),
                "name": _label(g, site),
                "node_type": "site",
                "brick_types": _brick_types(g, site),
                "markers": _stored_markers(g, site) or _seed_markers(g, site, "site"),
                "tags": {},
                "children": buildings or equip_nodes(None),
            }
        )
    return [_annotate_coverage(n) for n in roots]


def _require_mutations(graph: GraphService, allow: bool) -> None:
    if not allow:
        raise PermissionError("mutations disabled (set BLDGTS_ALLOW_MUTATIONS=true)")


def upsert_equipment(
    graph: GraphService,
    *,
    equipment_id: str,
    label: str | None,
    kind: str,
    parent_id: str | None,
    expected_revision: int | None,
    allow_mutations: bool,
) -> dict[str, Any]:
    _require_mutations(graph, allow_mutations)
    eid = _safe_id(equipment_id)
    equip = BLDG[eid]
    brick_class = _EQUIP_KINDS.get((kind or "ahu").strip().lower(), BRICK.Air_Handler_Unit)
    parent = BLDG[_safe_id(parent_id)] if parent_id else BLDG.Building_50

    def mutator(g: Graph) -> None:
        if (equip, RDF.type, None) not in g:
            g.add((equip, RDF.type, brick_class))
            g.add((equip, BTS.overlay, Literal(True, datatype=XSD.boolean)))
        else:
            # Do not strip existing types; ensure requested class present.
            g.add((equip, RDF.type, brick_class))
        g.set((equip, RDFS.label, Literal(label or eid)))
        g.set((equip, BRICK.isLocatedIn, parent))
        g.add((parent, BRICK.hasPart, equip))
        g.remove((equip, BTS.hidden, None))

    try:
        rev = graph.apply_mutation(
            mutator,
            note=f"upsert_equipment:{eid}",
            expected_revision=expected_revision,
        )
    except ConflictError as exc:
        return {
            "ok": False,
            "conflict": True,
            "revision": exc.current,
            "expected_revision": exc.expected,
        }
    graph.schedule_serialize()
    return {"ok": True, "revision": rev, "id": eid, "iri": str(equip)}


def upsert_point(
    graph: GraphService,
    *,
    point_id: str,
    label: str | None,
    owner_id: str,
    brick_class: str,
    timeseries_id: str | None,
    expected_revision: int | None,
    allow_mutations: bool,
) -> dict[str, Any]:
    _require_mutations(graph, allow_mutations)
    pid = _safe_id(point_id)
    oid = _safe_id(owner_id)
    point = BLDG[pid]
    owner = BLDG[oid]
    cls_key = (brick_class or "sensor").strip()
    cls = _POINT_KINDS.get(cls_key.lower()) or BRICK[cls_key]

    def mutator(g: Graph) -> None:
        existing_tid = _timeseries_id(g, point)
        if (point, RDF.type, None) not in g:
            g.add((point, RDF.type, cls))
            g.add((point, BTS.overlay, Literal(True, datatype=XSD.boolean)))
        else:
            g.add((point, RDF.type, cls))
        g.set((point, RDFS.label, Literal(label or pid)))
        g.set((point, BRICK.isPointOf, owner))
        g.add((owner, BRICK.hasPoint, point))
        g.remove((point, BTS.hidden, None))

        # Preserve existing timeseries reference; only create when missing.
        if existing_tid is None:
            tid = (timeseries_id or "").strip() or str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"urn:bldgts:overlay:{pid}")
            )
            ref = BNode()
            g.add((point, REF.hasExternalReference, ref))
            g.add((ref, RDF.type, REF.TimeseriesReference))
            g.add((ref, REF.hasTimeseriesId, Literal(tid)))
            g.add((ref, REF.storedAt, database_iri(g)))
        elif timeseries_id and timeseries_id.strip() != existing_tid:
            raise ValueError("refusing to change existing timeseries_id")

    try:
        rev = graph.apply_mutation(
            mutator,
            note=f"upsert_point:{pid}",
            expected_revision=expected_revision,
        )
    except ConflictError as exc:
        return {
            "ok": False,
            "conflict": True,
            "revision": exc.current,
            "expected_revision": exc.expected,
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "revision": graph.revision}
    graph.schedule_serialize()
    return {
        "ok": True,
        "revision": rev,
        "id": pid,
        "iri": str(point),
        "timeseries_id": _timeseries_id(graph.state.model, point),
    }


def hide_entity(
    graph: GraphService,
    *,
    entity_id: str,
    expected_revision: int | None,
    allow_mutations: bool,
) -> dict[str, Any]:
    """Soft-delete: hide from tree UI without removing TimeseriesReference triples."""
    _require_mutations(graph, allow_mutations)
    eid = _safe_id(entity_id)
    iri = BLDG[eid]

    def mutator(g: Graph) -> None:
        if (iri, RDF.type, None) not in g:
            raise ValueError(f"entity not found: {eid}")
        g.set((iri, BTS.hidden, Literal(True, datatype=XSD.boolean)))

    try:
        rev = graph.apply_mutation(
            mutator,
            note=f"hide:{eid}",
            expected_revision=expected_revision,
        )
    except ConflictError as exc:
        return {
            "ok": False,
            "conflict": True,
            "revision": exc.current,
            "expected_revision": exc.expected,
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "revision": graph.revision}
    graph.schedule_serialize()
    return {"ok": True, "revision": rev, "id": eid, "hidden": True}


def _level_for_entity(g: Graph, iri: URIRef) -> str:
    types = set(_brick_types(g, iri))
    if "Site" in types:
        return "site"
    if "Building" in types:
        return "building"
    if "Floor" in types:
        return "floor"
    if types & {
        "Sensor",
        "Setpoint",
        "Command",
        "Status",
        "Point",
    } or _timeseries_id(g, iri):
        return "point"
    if types & {
        "Air_Handler_Unit",
        "Variable_Air_Volume_Box",
        "Chiller",
        "Boiler",
        "Fan",
        "Pump",
    }:
        return "equip"
    return "equip"


def apply_markers(
    graph: GraphService,
    *,
    updates: list[dict[str, Any]],
    expected_revision: int | None,
    allow_mutations: bool,
) -> dict[str, Any]:
    """Batch Haystack marker writes for any tree entity."""
    _require_mutations(graph, allow_mutations)

    def mutator(g: Graph) -> None:
        for item in updates:
            eid = _safe_id(str(item.get("entity_id") or item.get("point_id") or ""))
            entity = BLDG[eid]
            if (entity, RDF.type, None) not in g:
                raise ValueError(f"entity not found: {eid}")
            if _is_hidden(g, entity):
                raise ValueError(f"entity is hidden: {eid}")
            level = str(item.get("level") or _level_for_entity(g, entity))
            allowed = catalog_for_level(level)
            raw = item.get("markers")
            if raw is None:
                raise ValueError("markers list required")
            markers = [str(m).strip() for m in raw if str(m).strip()]
            bad = [m for m in markers if m not in allowed]
            if bad:
                raise ValueError(f"markers not allowed for level {level}: {', '.join(bad)}")
            g.remove((entity, BTS.hasHaystackMarker, None))
            # Drop legacy shipping ops tags if present.
            g.remove((entity, BTS.opsStatus, None))
            g.remove((entity, BTS.opsMeta, None))
            g.remove((entity, BTS.opsNote, None))
            for marker in markers:
                g.add((entity, BTS.hasHaystackMarker, Literal(marker)))

    try:
        rev = graph.apply_mutation(
            mutator,
            note=f"haystack_markers:{len(updates)}",
            expected_revision=expected_revision,
        )
    except ConflictError as exc:
        return {
            "ok": False,
            "conflict": True,
            "revision": exc.current,
            "expected_revision": exc.expected,
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "revision": graph.revision}
    graph.schedule_serialize()
    return {"ok": True, "revision": rev, "updated": len(updates)}


def rename_entity(
    graph: GraphService,
    *,
    entity_id: str,
    label: str,
    expected_revision: int | None,
    allow_mutations: bool,
) -> dict[str, Any]:
    _require_mutations(graph, allow_mutations)
    eid = _safe_id(entity_id)
    text = label.strip()
    if not text:
        raise ValueError("label must not be empty")

    def mutator(g: Graph) -> None:
        entity = BLDG[eid]
        if (entity, RDF.type, None) not in g:
            raise ValueError(f"entity not found: {eid}")
        if _is_hidden(g, entity):
            raise ValueError(f"entity is hidden: {eid}")
        g.set((entity, RDFS.label, Literal(text)))

    try:
        rev = graph.apply_mutation(
            mutator,
            note=f"rename:{eid}",
            expected_revision=expected_revision,
        )
    except ConflictError as exc:
        return {
            "ok": False,
            "conflict": True,
            "revision": exc.current,
            "expected_revision": exc.expected,
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "revision": graph.revision}
    graph.schedule_serialize()
    return {"ok": True, "revision": rev, "id": eid, "label": text}


def dashboard(graph: GraphService) -> dict[str, Any]:
    """Haystack marker coverage across historized points (stored markers only)."""
    g = graph.state.model
    points: list[dict[str, Any]] = []
    marker_counts: dict[str, int] = {}
    for s, _, _ in g.triples((None, REF.hasExternalReference, None)):
        point = URIRef(s)
        if _is_hidden(g, point):
            continue
        markers = _stored_markers(g, point)
        for marker in markers:
            marker_counts[marker] = marker_counts.get(marker, 0) + 1
        points.append(
            {
                "id": _local(point),
                "name": _label(g, point),
                "timeseries_id": _timeseries_id(g, point),
                "markers": markers,
                "complete": _point_complete(markers),
            }
        )
    points.sort(key=lambda p: p["name"].lower())
    tagged = sum(1 for p in points if p["markers"])
    complete = sum(1 for p in points if p["complete"])
    status = _coverage_status(total=len(points), complete=complete)
    return {
        "revision": graph.revision,
        "status": status,
        "totals": {
            "items": len(points),
            "tagged": tagged,
            "complete": complete,
            "untagged": len(points) - tagged,
            "incomplete": len(points) - complete,
            "distinct_markers": len(marker_counts),
        },
        "marker_counts": dict(sorted(marker_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "items": points,
    }
