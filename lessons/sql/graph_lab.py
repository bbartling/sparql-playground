"""Offline, bounded Brick reference exercises; never contacts a historian or remote graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bldgts.graph.sparql_guard import SparqlRejected, prepare_sparql, run_prepared
from bldgts.settings import Settings
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

HERE = Path(__file__).resolve().parent
REF = Namespace("https://brickschema.org/schema/Brick/ref#")
EX = Namespace("https://example.org/course#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")
UNIT = Namespace("http://qudt.org/vocab/unit/")
UNIT_IRIS = {
    "Pa": UNIT.PA,
    "bool": UNIT.UNITLESS,
    "%": UNIT.PERCENT,
    "kW": UNIT.KiloW,
    "degC": UNIT.DEG_C,
}


def load_graph() -> Graph:
    return Graph().parse(HERE / "model.ttl", format="turtle")


def resolve(graph: Graph, point: URIRef) -> dict[str, str]:
    refs = list(graph.objects(point, REF.hasExternalReference))
    if len(refs) != 1:
        raise ValueError("point must have exactly one external reference")
    ids = list(graph.objects(refs[0], REF.hasTimeseriesId))
    databases = list(graph.objects(refs[0], REF.storedAt))
    if len(ids) != 1 or len(databases) != 1:
        raise ValueError("external reference must have one id and one database")
    if not isinstance(ids[0], Literal) or not isinstance(databases[0], URIRef):
        raise ValueError("timeseries id must be a literal and database must be an IRI")
    if (databases[0], RDF.type, REF.Database) not in graph:
        raise ValueError("external database must be typed ref:Database")
    if (refs[0], RDF.type, REF.TimeseriesReference) not in graph:
        raise ValueError("external reference has the wrong RDF type")
    return {"point": str(point), "timeseries_id": str(ids[0]), "database": str(databases[0])}


def check_graph(graph: Graph) -> int:
    fixture = json.loads((HERE / "fixture.json").read_text())
    for point in fixture["points"]:
        iri = EX["point_" + point["point_id"]]
        resolved = resolve(graph, iri)
        if resolved["timeseries_id"] != point["point_id"] or resolved["database"] != str(
            EX.course_database
        ):
            raise ValueError("model and SQL fixture identities differ")
        expected = {
            EX.role: Literal(point["role"]),
            EX.site_id: Literal(point["site_id"]),
            BRICK.isPointOf: EX["equipment_" + point["equipment_id"]],
            BRICK.hasUnit: UNIT_IRIS[point["unit"]],
        }
        for predicate, value in expected.items():
            if list(graph.objects(iri, predicate)) != [value]:
                raise ValueError(f"model and SQL metadata differ for {predicate}")
    if len(set(graph.subjects(REF.hasExternalReference, None))) != len(fixture["points"]):
        raise ValueError("unexpected or missing model point")
    print(
        json.dumps(
            {
                "status": "PASS",
                "points": len(fixture["points"]),
                "evidence": "offline RDF-to-SQL-fixture binding; no live DB query",
            }
        )
    )
    return len(fixture["points"])


def execute(graph: Graph, text: str) -> dict:
    settings = Settings(sparql_max_query_chars=20000, sparql_max_rows=1000)
    prepared = prepare_sparql(text, settings)
    if prepared.query.algebra.name not in {"SelectQuery", "AskQuery"}:
        raise SparqlRejected("course exercises accept SELECT/ASK only")
    result = run_prepared(graph, prepared)
    # RDFLib serializes actual RDF term kinds, not guesses from lexical strings.
    body = json.loads(result.serialize(format="json"))
    if len(body.get("results", {}).get("bindings", [])) > 1000:
        raise ValueError("query result exceeds course row cap; narrow the query")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--resolve", metavar="POINT_IRI")
    args = parser.parse_args()
    graph = load_graph()
    if args.check:
        check_graph(graph)
    elif args.resolve:
        print(json.dumps(resolve(graph, URIRef(args.resolve)), indent=2))
    elif args.query:
        print(json.dumps(execute(graph, args.query.read_text()), indent=2))
    else:
        parser.error("supply a .rq file, --check, or --resolve POINT_IRI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
