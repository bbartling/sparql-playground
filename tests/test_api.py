from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings


@pytest.fixture
def client(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    assert client.get("/health").json()["status"] == "ok"


def test_sparql_examples(client: TestClient):
    ex = client.get("/api/sparql/examples").json()["examples"]
    assert ex
    for item in ex:
        r = client.post("/api/sparql", json={"query": item["query"]})
        assert r.status_code == 200, item["id"]


def test_sparql_rejects_update(client: TestClient):
    r = client.post(
        "/api/sparql", json={"query": 'INSERT DATA { <http://ex/s> <http://ex/p> "1" }'}
    )
    assert r.status_code == 400


def test_fc1_points(client: TestClient):
    eq = "AHU_1"
    r1 = client.get(
        f"/api/equipment/{eq}/points",
        params={"brick_class": "Supply_Air_Static_Pressure_Sensor"},
    )
    assert len(r1.json()["points"]) == 1
    r2 = client.get(
        f"/api/equipment/{eq}/points",
        params={"tags": "Supply,Air,Static,Pressure,Setpoint"},
    )
    assert len(r2.json()["points"]) == 1
    r3 = client.get(
        f"/api/equipment/{eq}/points",
        params={"brick_class": "Fan_Speed_Command", "parent_class": "Supply_Fan"},
    )
    assert len(r3.json()["points"]) == 1


def test_timeseries_and_errors(client: TestClient, settings: Settings):
    pt = client.get(
        "/api/equipment/AHU_1/points", params={"brick_class": "Supply_Air_Static_Pressure_Sensor"}
    ).json()["points"][0]
    ts = client.get(f"/api/points/{pt['point_id']}/timeseries", params={"limit": 10})
    assert ts.status_code == 200
    samples = ts.json()["samples"]
    assert samples == sorted(samples, key=lambda s: s["ts"])

    r404 = client.get("/api/equipment/NO_SUCH_EQUIP/points")
    assert r404.status_code == 404

    r422 = client.get("/api/equipment/AHU_1/points", params={"brick_class": "NotAClass"})
    assert r422.status_code == 422


def test_mutations_gated(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post("/api/model/points", json={"points": []})
        assert r.status_code == 403


def test_mutations_enabled(settings: Settings, tmp_path: Path):
    settings.allow_mutations = True
    settings.serialize_on_mutation = True
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        body = {
            "points": [
                {
                    "point_id": "TEST_PT",
                    "label": "Test",
                    "brick_class": "Sensor",
                    "owner_id": "AHU_1",
                    "timeseries_id": "00000000-0000-0000-0000-000000000099",
                    "unit": None,
                }
            ]
        }
        r = client.post("/api/model/points", json=body)
        assert r.status_code == 200
        q = client.post(
            "/api/sparql",
            json={
                "query": (
                    "PREFIX bldg: <https://example.org/openfdd/BUILDING_50#> "
                    "ASK { bldg:TEST_PT ?p ?o }"
                )
            },
        )
        assert q.status_code == 200
        assert q.json()["results"].get("boolean") is True
        client.post("/api/model/flush")
        assert settings.snapshot_path.exists()
        assert not list(settings.snapshot_path.parent.glob("*.tmp"))


def test_timeseries_negative_cases(client: TestClient):
    from rdflib import Literal

    from brickts.graph.namespaces import BLDG, BRICK, RDF, REF

    assert client.get("/api/points/NO_SUCH_POINT/timeseries").status_code == 404
    assert (
        client.post(
            "/api/sparql", json={"query": "SELECT * WHERE { SERVICE <http://x/> { ?s ?p ?o } }"}
        ).status_code
        == 400
    )

    graph = client.app.state.ctx.graph
    model = graph.state.model
    model.add((BLDG.NO_REF_PT, RDF.type, BRICK.Temperature_Sensor))
    model.add((BLDG.NO_REF_PT, BRICK.isPointOf, BLDG.AHU_1))
    ref = next(model.objects(BLDG.AHU_1_DA_P, REF.hasExternalReference))
    model.add((ref, REF.hasTimeseriesId, Literal("second-id")))
    graph._state = graph._rebuild_union(model)

    assert client.get("/api/points/NO_REF_PT/timeseries").status_code == 409
    assert client.get("/api/points/AHU_1_DA_P/timeseries").status_code == 409
