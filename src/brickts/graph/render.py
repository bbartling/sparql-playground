from __future__ import annotations

import csv
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef

from brickts.graph.namespaces import BLDG, BRICK, RDF, RDFS, REF, UNIT


def _unit_uri(unit: str) -> URIRef | None:
    if not unit:
        return None
    return UNIT[unit]


def render_model(site_path: Path, points_csv: Path, db_node: str = "timeseries_db") -> Graph:
    g = Graph()
    g.parse(site_path, format="turtle")
    db_iri = BLDG[db_node]

    with points_csv.open(newline="") as f:
        for row in csv.DictReader(f):
            point_iri = BLDG[row["point_id"]]
            owner_iri = BLDG[row["owner_id"]]
            g.add((point_iri, RDF.type, BRICK[row["brick_class"]]))
            g.add((point_iri, RDFS.label, Literal(row["label"])))
            g.add((point_iri, BRICK.isPointOf, owner_iri))
            g.add((owner_iri, BRICK.hasPoint, point_iri))
            u = _unit_uri(row["unit"].strip())
            if u is not None:
                g.add((point_iri, BRICK.hasUnit, u))
            ref = BNode()
            g.add((point_iri, REF.hasExternalReference, ref))
            g.add((ref, RDF.type, REF.TimeseriesReference))
            g.add((ref, REF.hasTimeseriesId, Literal(row["timeseries_id"])))
            g.add((ref, REF.storedAt, db_iri))
    return g


def write_turtle(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.serialize(format="turtle"))
