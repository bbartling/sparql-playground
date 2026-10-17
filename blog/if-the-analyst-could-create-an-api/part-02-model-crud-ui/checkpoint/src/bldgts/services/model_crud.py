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
from bldgts.haystack.metadata import (
    PROFILE,
    PROFILE_LIMITS,
    entity_level,
    metadata,
    replace_metadata,
    validate_entity,
)
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
    "Status": ("point",),
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
                "floor": ("space", "floor"),
                "space": ("space",),
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


def _annotate_coverage(node: dict[str, Any], g: Graph) -> dict[str, Any]:
    """Report required errors separately from recommendations, then roll up."""
    iri = URIRef(node["iri"])
    level = "equip" if node["node_type"] == "equipment" else node["node_type"]
    node.update(validate_entity(g, iri, level))
    node["markers"] = _stored_markers(g, iri)
    node["hints"] = _seed_markers(g, iri, level)
    node["tagged"] = bool(node["markers"] or node["metadata"])
    kids = [_annotate_coverage(child, g) for child in node.get("children") or []]
    node["children"] = kids
    is_point = node["node_type"] == "point"
    node["points_total"] = 1 if is_point else sum(c["points_total"] for c in kids)
    node["points_complete"] = (
        int(node["complete"]) if is_point else sum(c["points_complete"] for c in kids)
    )
    node["error_count"] = sum(i["severity"] == "error" for i in node["issues"]) + sum(
        c["error_count"] for c in kids
    )
    node["warning_count"] = sum(i["severity"] == "warning" for i in node["issues"]) + sum(
        c["warning_count"] for c in kids
    )
    node["coverage"] = (
        "red" if node["error_count"] else ("yellow" if node["warning_count"] else "green")
    )
    return node


def build_tree(graph: GraphService) -> list[dict[str, Any]]:
    """Project the complete visible model into one deterministic, acyclic tree.

    Resolve classes through Brick rather than a short equipment-name allowlist.
    Inverse and forward containment/location edges are equivalent inputs. Every
    visible model entity appears once, including unattached records as roots;
    malformed cycles or multiple parents cannot hide points or recurse forever.
    """
    g = graph.state.model
    ontology = graph.ontology
    levels: dict[URIRef, str] = {}
    candidates = set(g.subjects(RDF.type, None)) | set(g.subjects(REF.hasExternalReference, None))
    for entity in sorted(candidates, key=str):
        if not isinstance(entity, URIRef) or _is_hidden(g, entity):
            continue
        try:
            levels[entity] = entity_level(g, entity, ontology)
        except ValueError:
            continue  # Database, unit and metadata-definition records are not tree rows.

    def parent_candidates(entity: URIRef) -> list[URIRef]:
        if levels[entity] == "point":
            groups = (
                g.objects(entity, BRICK.isPointOf),
                g.subjects(BRICK.hasPoint, entity),
                g.objects(entity, BRICK.isLocatedIn),
            )
        else:
            groups = (
                g.objects(entity, BRICK.isPartOf),
                g.subjects(BRICK.hasPart, entity),
                g.objects(entity, BRICK.isLocatedIn),
                g.subjects(BRICK.hasLocation, entity),
            )
        ordered: list[URIRef] = []
        for group in groups:
            for parent in sorted(set(group), key=str):
                if (
                    parent in levels
                    and parent != entity
                    and levels[parent] != "point"
                    and parent not in ordered
                ):
                    ordered.append(parent)
        return ordered

    parents: dict[URIRef, URIRef] = {}
    for entity in sorted(levels, key=str):
        for parent in parent_candidates(entity):
            cursor = parent
            seen = {entity}
            while cursor not in seen:
                seen.add(cursor)
                if cursor not in parents:
                    parents[entity] = parent
                    break
                cursor = parents[cursor]
            if entity in parents:
                break

    children: dict[URIRef, list[URIRef]] = {entity: [] for entity in levels}
    for entity, parent in parents.items():
        children[parent].append(entity)
    order = {"site": 0, "building": 1, "floor": 2, "space": 3, "equip": 4, "part": 4, "point": 5}

    def sort_key(entity: URIRef) -> tuple[int, str, str]:
        return order[levels[entity]], _label(g, entity).lower(), str(entity)

    def node(entity: URIRef) -> dict[str, Any]:
        level = levels[entity]
        if level in {"equip", "part"}:
            parent = parents.get(entity)
            level = "part" if parent and levels[parent] in {"equip", "part"} else "equip"
        tid = _timeseries_id(g, entity) if level == "point" else None
        return {
            "id": _local(entity),
            "iri": str(entity),
            "name": _label(g, entity),
            "node_type": "equipment" if level == "equip" else level,
            "brick_types": _brick_types(g, entity),
            "tags": {"timeseries_id": tid} if tid else {},
            "children": [node(child) for child in sorted(children[entity], key=sort_key)],
        }

    roots = sorted((entity for entity in levels if entity not in parents), key=sort_key)
    return [_annotate_coverage(node(entity), g) for entity in roots]


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
        if entity_level(g, owner) not in {"equip", "part"} or _is_hidden(g, owner):
            raise ValueError("point owner must be existing visible equipment")
        existing_tid = _timeseries_id(g, point)
        if (point, RDF.type, None) not in g:
            g.add((point, RDF.type, cls))
            g.add((point, BTS.overlay, Literal(True, datatype=XSD.boolean)))
        else:
            g.add((point, RDF.type, cls))
        g.set((point, RDFS.label, Literal(label or pid)))
        g.remove((None, BRICK.hasPoint, point))
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


def _validated_markers(g: Graph, entity: URIRef, item: dict[str, Any]) -> list[str]:
    if _is_hidden(g, entity):
        raise ValueError(f"entity is hidden: {_local(entity)}")
    level = entity_level(g, entity)
    requested = str(item.get("level") or level)
    requested = "equip" if requested == "equipment" else requested
    if requested != level:
        raise ValueError(f"entity level is {level}, not {requested}")
    allowed = catalog_for_level(level)
    raw = item.get("markers")
    if not isinstance(raw, list) or any(not isinstance(m, str) for m in raw):
        raise ValueError("markers must be a list of strings")
    markers = list(dict.fromkeys(m.strip() for m in raw if m.strip()))
    bad = [m for m in markers if m not in allowed]
    if bad:
        raise ValueError(f"markers not allowed for level {level}: {', '.join(bad)}")
    return markers


def _write_markers(g: Graph, entity: URIRef, markers: list[str]) -> None:
    g.remove((entity, BTS.hasHaystackMarker, None))
    for predicate in (BTS.opsStatus, BTS.opsMeta, BTS.opsNote):
        g.remove((entity, predicate, None))
    for marker in markers:
        g.add((entity, BTS.hasHaystackMarker, Literal(marker)))


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
            markers = _validated_markers(g, entity, item)
            _write_markers(g, entity, markers)

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
        values = metadata(g, entity)
        if "dis" in values:
            values["dis"] = {"kind": "Str", "value": text}
            replace_metadata(g, entity, values)

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


def _bridge_point_ownership(g: Graph, entity: URIRef) -> None:
    """Keep the legacy Brick query/tree ownership aligned with an explicit ref.

    Unresolved drafts keep their prior placement so a user can finish editing
    without losing the row. Structural Brick links are a compatibility bridge;
    they do not manufacture or verify Haystack metadata.
    """
    if entity_level(g, entity) != "point":
        return
    values = metadata(g, entity)
    equip_ref = values.get("equipRef", {})
    if equip_ref.get("kind") != "Ref":
        return
    raw = str(equip_ref["value"])
    owner = URIRef(raw) if ":" in raw else BLDG[raw]
    try:
        level = entity_level(g, owner)
    except ValueError:
        return
    if level not in {"equip", "part"} or _is_hidden(g, owner):
        return
    site_ref = values.get("siteRef", {})
    owner_site = metadata(g, owner).get("siteRef", {})
    if site_ref.get("kind") == "Ref" and owner_site.get("kind") == "Ref":

        def ref_iri(value: Any) -> URIRef:
            text = str(value)
            return URIRef(text) if ":" in text else BLDG[text]

        if ref_iri(site_ref["value"]) != ref_iri(owner_site["value"]):
            return
    g.remove((None, BRICK.hasPoint, entity))
    g.set((entity, BRICK.isPointOf, owner))
    g.add((owner, BRICK.hasPoint, entity))


def apply_metadata(
    graph: GraphService,
    *,
    updates: list[dict[str, Any]],
    expected_revision: int | None,
    allow_mutations: bool,
) -> dict[str, Any]:
    """Atomic replacement of typed tags, optionally with their marker set.

    Semantically incomplete models may be saved while being authored; tree
    issues describe their errors. Malformed types and spoofed levels fail the
    entire copy-on-write batch, leaving both metadata and revision unchanged.
    """
    _require_mutations(graph, allow_mutations)

    def mutator(g: Graph) -> None:
        for item in updates:
            eid = _safe_id(str(item.get("entity_id") or ""))
            entity = BLDG[eid]
            entity_level(g, entity)
            if _is_hidden(g, entity):
                raise ValueError(f"entity is hidden: {eid}")
            if "markers" in item:
                _write_markers(g, entity, _validated_markers(g, entity, item))
            values = item.get("metadata")
            replace_metadata(g, entity, values)
            dis = values.get("dis", {})
            if dis.get("kind") == "Str":
                g.set((entity, RDFS.label, Literal(dis["value"].strip())))
        # Resolve after the full batch so referenced equipment metadata can be
        # authored in either order alongside the point's explicit ownership.
        for item in updates:
            _bridge_point_ownership(g, BLDG[_safe_id(str(item.get("entity_id") or ""))])

    try:
        rev = graph.apply_mutation(
            mutator, note=f"haystack_metadata:{len(updates)}", expected_revision=expected_revision
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


def dashboard(graph: GraphService) -> dict[str, Any]:
    """Explicit point modeling status for the supported Haystack profile."""
    g = graph.state.model
    points: list[dict[str, Any]] = []
    marker_counts: dict[str, int] = {}
    for s in set(g.subjects(REF.hasExternalReference, None)):
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
                **validate_entity(g, point, "point"),
            }
        )
    points.sort(key=lambda p: p["name"].lower())
    tagged = sum(bool(p["markers"] or p["metadata"]) for p in points)
    complete = sum(p["complete"] for p in points)
    errors = sum(i["severity"] == "error" for p in points for i in p["issues"])
    warnings = sum(i["severity"] == "warning" for p in points for i in p["issues"])
    status = "red" if errors else ("yellow" if warnings else "green")
    return {
        "revision": graph.revision,
        "status": status,
        "validation_profile": PROFILE,
        "validation_limits": PROFILE_LIMITS,
        "totals": {
            "items": len(points),
            "tagged": tagged,
            "complete": complete,
            "untagged": len(points) - tagged,
            "incomplete": len(points) - complete,
            "distinct_markers": len(marker_counts),
            "errors": errors,
            "warnings": warnings,
        },
        "marker_counts": dict(sorted(marker_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "items": points,
    }
