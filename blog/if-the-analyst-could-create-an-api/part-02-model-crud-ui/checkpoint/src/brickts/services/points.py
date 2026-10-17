from __future__ import annotations

import re
from dataclasses import dataclass

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS

from brickts.graph.namespaces import BLDG, BRICK, RDF, REF

ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
CLASS_RE = re.compile(r"^[A-Z][A-Za-z0-9_]{0,127}$")
TAG_RE = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass
class PointSummary:
    point_id: str
    label: str
    brick_class: str
    owner_id: str
    timeseries_id: str | None
    unit: str | None


def _local_name(uri: URIRef) -> str:
    s = str(uri)
    if "#" in s:
        return s.rsplit("#", 1)[-1]
    return s.rsplit("/", 1)[-1]


def _class_local(g: Graph, point: URIRef) -> str | None:
    for o in g.objects(point, RDF.type):
        if isinstance(o, URIRef) and str(o).startswith(str(BRICK)):
            name = _local_name(o)
            if name != "Point":
                return name
    return None


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
    cls = BRICK[class_name]
    q = f"""
    ASK {{
      <{cls}> (rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?p .
      ?p (rdfs:subClassOf|owl:equivalentClass)*<{BRICK.Point}> .
    }}
    """
    return bool(union.query(q))


def list_equipment(union: Graph) -> list[dict]:
    q = """
    SELECT ?equip ?label WHERE {
      ?equip a ?cls .
      FILTER(STRSTARTS(STR(?equip), "https://example.org/openfdd/BUILDING_50#"))
      ?cls (rdfs:subClassOf|owl:equivalentClass)* brick:Equipment .
      OPTIONAL { ?equip rdfs:label ?label }
    }
    ORDER BY ?equip
    """
    out = []
    for row in union.query(q, initNs={"brick": BRICK, "rdfs": RDFS, "owl": OWL}):
        eid = _local_name(row.equip)
        if eid.startswith("Zone_"):
            continue
        out.append({"equipment_id": eid, "label": str(row.label) if row.label else eid})
    return out


def _equipment_uri(equipment_id: str) -> URIRef:
    return BLDG[equipment_id]


def _point_in_scope(
    union: Graph,
    point: URIRef,
    equipment: URIRef,
    *,
    include_fed_zones: bool,
) -> bool:
    q = """
    ASK {
      { ?point brick:isPointOf ?equipment }
      UNION
      { ?point brick:isPointOf ?part . ?part (brick:isPartOf|^brick:hasPart)* ?equipment }
      UNION
      { ?point brick:isPointOf ?zone . ?zone (brick:isFedBy|^brick:feeds)* ?equipment }
    }
    """
    if not include_fed_zones:
        q = """
        ASK {
          { ?point brick:isPointOf ?equipment }
          UNION
          { ?point brick:isPointOf ?part . ?part (brick:isPartOf|^brick:hasPart)* ?equipment }
        }
        """
    return bool(
        union.query(
            q,
            initNs={"brick": BRICK},
            initBindings={"point": point, "equipment": equipment},
        )
    )


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
    validate_equipment_id(equipment_id)
    equipment = _equipment_uri(equipment_id)
    if brick_class:
        validate_class_name(brick_class)
        if not is_point_subclass(union, brick_class):
            raise ValueError("unknown or non-point class")
    if parent_class:
        validate_class_name(parent_class)
    if tags:
        validate_tags(tags)

    candidates = set(union.subjects(RDF.type, None))
    results: list[PointSummary] = []
    for p in candidates:
        if not isinstance(p, URIRef) or not str(p).startswith(str(BLDG)):
            continue
        if not _point_in_scope(union, p, equipment, include_fed_zones=include_fed_zones):
            continue
        cls_name = _class_local(union, p)
        if cls_name is None:
            continue
        if brick_class:
            target = BRICK[brick_class]
            path = (
                "(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)*"
                if include_subclasses
                else ""
            )
            ask = f"""
            ASK {{ <{p}> a/{path} <{target}> . }}
            """
            if not bool(union.query(ask, initNs={"rdfs": RDFS, "owl": OWL})):
                continue
        if parent_class:
            owner = next(union.objects(p, BRICK.isPointOf), None)
            if owner is None:
                continue
            ptarget = BRICK[parent_class]
            ask = (
                f"ASK {{ <{owner}> a/(rdfs:subClassOf|owl:equivalentClass|"
                f"^owl:equivalentClass)* <{ptarget}> . }}"
            )
            if not bool(union.query(ask, initNs={"rdfs": RDFS, "owl": OWL})):
                continue
        if tags:
            tag_ns = "https://brickschema.org/schema/BrickTag#"
            tag_uris = [URIRef(tag_ns + t) for t in tags]
            point_tags = {o for o in union.objects(p, BRICK.hasAssociatedTag)}
            if not all(t in point_tags for t in tag_uris):
                # Also match via class tags
                cls_uri = BRICK[cls_name]
                class_tags = {o for o in union.objects(cls_uri, BRICK.hasAssociatedTag)}
                if not all(t in class_tags for t in tag_uris):
                    continue
        pid = _local_name(p)
        label = next(union.objects(p, RDFS.label), pid)
        owner = next(union.objects(p, BRICK.isPointOf), None)
        owner_id = _local_name(owner) if owner else ""
        ts_id = None
        for ref in union.objects(p, REF.hasExternalReference):
            ids = list(union.objects(ref, REF.hasTimeseriesId))
            if ids:
                ts_id = str(ids[0])
                break
        unit = None
        u = next(union.objects(p, BRICK.hasUnit), None)
        if u is not None:
            unit = _local_name(u)
        results.append(
            PointSummary(
                point_id=pid,
                label=str(label),
                brick_class=cls_name,
                owner_id=owner_id,
                timeseries_id=ts_id,
                unit=unit,
            )
        )
    results.sort(key=lambda x: x.point_id)
    return results


def get_point(union: Graph, point_id: str) -> PointSummary | None:
    if not ID_RE.match(point_id):
        return None
    p = BLDG[point_id]
    if (p, RDF.type, None) not in union and not list(union.triples((p, RDF.type, None))):
        return None
    cls_name = _class_local(union, p)
    if cls_name is None:
        return None
    label = next(union.objects(p, RDFS.label), point_id)
    owner = next(union.objects(p, BRICK.isPointOf), None)
    owner_id = _local_name(owner) if owner else ""
    ts_id = None
    for ref in union.objects(p, REF.hasExternalReference):
        ids = list(union.objects(ref, REF.hasTimeseriesId))
        if ids:
            ts_id = str(ids[0])
            break
    unit = None
    u = next(union.objects(p, BRICK.hasUnit), None)
    if u is not None:
        unit = _local_name(u)
    return PointSummary(
        point_id=point_id,
        label=str(label),
        brick_class=cls_name,
        owner_id=owner_id,
        timeseries_id=ts_id,
        unit=unit,
    )
