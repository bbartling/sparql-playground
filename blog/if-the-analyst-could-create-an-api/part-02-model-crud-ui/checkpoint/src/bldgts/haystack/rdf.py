"""Helpers for writing application Haystack markers and typed tags into RDF."""

from __future__ import annotations

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from bldgts.graph.namespaces import BLDG, BTS


def add_markers(g: Graph, entity: URIRef, markers: list[str] | tuple[str, ...]) -> None:
    g.remove((entity, BTS.hasHaystackMarker, None))
    for marker in markers:
        g.add((entity, BTS.hasHaystackMarker, Literal(marker)))


def add_tag(g: Graph, entity: URIRef, name: str, kind: str, value: str | float | bool) -> None:
    node = BNode()
    g.add((entity, BTS.hasHaystackTag, node))
    g.add((node, BTS.tagName, Literal(name)))
    g.add((node, BTS.tagKind, Literal(kind)))
    if kind == "Ref":
        ref = value if isinstance(value, URIRef) else BLDG[str(value)]
        g.add((node, BTS.tagValue, ref))
    elif kind == "Number":
        g.add((node, BTS.tagValue, Literal(float(value), datatype=XSD.decimal)))
    elif kind == "Bool":
        g.add((node, BTS.tagValue, Literal(bool(value), datatype=XSD.boolean)))
    else:
        g.add((node, BTS.tagValue, Literal(str(value))))


def declare_entity(g: Graph, entity: URIRef) -> None:
    """Minimal typed presence so the entity is a first-class model resource."""
    g.add((entity, RDF.type, BTS.Entity))
