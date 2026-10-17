from bldgts.api.app import create_app
from bldgts.ingest import bootstrap_all
from bldgts.settings import Settings
from fastapi.testclient import TestClient


def test_integrity_endpoint_reports_status(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        resp = client.get("/api/model/integrity")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["status"] in {"green", "yellow", "red"}
        assert "issues" in body
        assert "error_count" in body


def test_tree_exposes_coverage_flags(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        tree = client.get("/api/model/tree").json()["tree"]
        assert tree
        # Seed graph has points with timeseries refs but typically no stored Haystack markers yet.
        flat = []

        def walk(nodes):
            for n in nodes:
                flat.append(n)
                walk(n.get("children") or [])

        walk(tree)
        points = [n for n in flat if n["node_type"] == "point"]
        assert points
        assert all("complete" in p and "coverage" in p for p in points)
        assert any(n.get("coverage") in {"green", "yellow", "red"} for n in flat)


def test_repeated_display_labels_do_not_make_model_unhealthy():
    from bldgts.graph.namespaces import BLDG, BRICK, REF
    from bldgts.graph.validate import run_rdf_integrity
    from rdflib import Graph, Literal
    from rdflib.namespace import RDF, RDFS

    model = Graph()
    for number in (1, 2):
        point, owner, reference = (
            BLDG[f"point{number}"],
            BLDG[f"ahu{number}"],
            BLDG[f"reference{number}"],
        )
        model.add((point, RDF.type, BRICK.Point))
        model.add((point, RDFS.label, Literal("Discharge temperature")))
        model.add((point, BRICK.isPointOf, owner))
        model.add((point, REF.hasExternalReference, reference))
        model.add((reference, REF.hasTimeseriesId, Literal(f"opaque-{number}")))
    report = run_rdf_integrity(model)
    assert report["status"] == "green"
    assert report["issues"] == []
