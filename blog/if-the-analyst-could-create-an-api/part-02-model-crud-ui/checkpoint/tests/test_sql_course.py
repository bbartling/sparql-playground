from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from bldgts.graph.sparql_guard import SparqlRejected
from rdflib import Literal
from rdflib.namespace import XSD

COURSE = Path(__file__).resolve().parents[1] / "lessons" / "sql"


def module(name):
    spec = importlib.util.spec_from_file_location(name, COURSE / f"{name}.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_course_structure():
    assert module("validate_course").validate() == []


def test_all_graph_bindings_match_frozen_sql_fixture():
    graph_lab = module("graph_lab")
    graph = graph_lab.load_graph()
    assert graph_lab.check_graph(graph) == 42
    fixture = json.loads((COURSE / "fixture.json").read_text())
    point = graph_lab.EX["point_" + fixture["points"][0]["point_id"]]
    ref = next(graph.objects(point, graph_lab.REF.hasExternalReference))
    graph.add((ref, graph_lab.REF.hasTimeseriesId, Literal("duplicate")))
    with pytest.raises(ValueError, match="one id"):
        graph_lab.resolve(graph, point)


def test_sparql_examples_are_executed_and_typed():
    graph_lab = module("graph_lab")
    graph = graph_lab.load_graph()
    expected = {
        "day50_triples": 6,
        "day51_ahus": 3,
        "day52_owned_points": 42,
        "day53_power_refs": 3,
        "day54_role_units": 14,
    }
    for path in sorted((COURSE / "sparql").glob("*.rq")):
        rows = graph_lab.execute(graph, path.read_text())["results"]["bindings"]
        assert len(rows) == expected[path.stem]
    bindings = graph_lab.execute(
        graph,
        """
        PREFIX ex: <https://example.org/course#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT (ex:course_database AS ?iri) ("https://example.org/text" AS ?text)
               (7 AS ?number) (true AS ?flag) WHERE {}
    """,
    )["results"]["bindings"][0]
    assert bindings["iri"]["type"] == "uri"
    assert bindings["text"]["type"] == "literal"
    assert bindings["number"]["datatype"] == str(XSD.integer)
    assert bindings["flag"]["datatype"] == str(XSD.boolean)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * WHERE { SERVICE <http://127.0.0.1:9> { ?s ?p ?o } }",
        "SELECT * FROM <https://example.org/remote> WHERE { ?s ?p ?o }",
        "INSERT DATA { <urn:s> <urn:p> <urn:o> }",
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
    ],
)
def test_course_rejects_remote_mutating_or_non_table_queries(query):
    graph_lab = module("graph_lab")
    with pytest.raises(SparqlRejected):
        graph_lab.execute(graph_lab.load_graph(), query)


def test_wrong_database_guard_stops_before_loading_sql(monkeypatch):
    lab = module("lab")
    calls = []
    monkeypatch.setattr(lab, "environment", lambda: {"COURSE_MODE": "native"})

    def wrong_database(sql, env, **kwargs):
        calls.append(sql)
        return "unrelated_application\n"

    monkeypatch.setattr(lab, "query", wrong_database)
    with pytest.raises(ValueError, match="Refusing course command"):
        lab.main(["load"])
    assert calls == ["SELECT current_database();"]


def test_native_mode_never_controls_shared_server(monkeypatch):
    lab = module("lab")
    monkeypatch.setattr(lab, "environment", lambda: {"COURSE_MODE": "native"})
    with pytest.raises(SystemExit) as error:
        lab.main(["down"])
    assert error.value.code == 2


def test_model_owner_and_unit_mismatch_is_detected():
    graph_lab = module("graph_lab")
    graph = graph_lab.load_graph()
    fixture = json.loads((COURSE / "fixture.json").read_text())
    iri = graph_lab.EX["point_" + fixture["points"][0]["point_id"]]
    graph.set((iri, graph_lab.EX.site_id, Literal("SYN-SOUTH")))
    with pytest.raises(ValueError, match="metadata differ"):
        graph_lab.check_graph(graph)


def test_graph_row_cap_and_boolean_results():
    graph_lab = module("graph_lab")
    graph = graph_lab.load_graph()
    assert graph_lab.execute(graph, "ASK { ?s ?p ?o }")["boolean"] is True
    assert graph_lab.execute(graph, "ASK { <urn:absent> ?p ?o }")["boolean"] is False
    values = " ".join(str(i) for i in range(1001))
    with pytest.raises(ValueError, match="row cap"):
        graph_lab.execute(graph, "SELECT ?n WHERE { VALUES ?n { " + values + " } }")
