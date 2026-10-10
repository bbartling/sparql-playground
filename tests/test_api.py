from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings

RQ = Path(__file__).resolve().parents[1] / "scripts" / "sparql" / "02_fc1_points.rq"


@pytest.fixture
def client(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["ready"] is True
    assert client.get("/hello").status_code == 404


def test_sparql_and_upload(client: TestClient):
    bad = client.post(
        "/api/sparql",
        json={"query": 'INSERT DATA { <http://ex/s> <http://ex/p> "1" }'},
    )
    assert bad.status_code == 400

    text = RQ.read_text(encoding="utf-8")
    uploaded = client.post(
        "/api/sparql/upload",
        files={"file": ("02_fc1_points.rq", text.encode("utf-8"), "text/plain")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["meta"]["row_count"] >= 3

    posted = client.post("/api/sparql", json={"query": text})
    assert posted.status_code == 200
    assert posted.json()["meta"]["row_count"] >= 3

    assert client.get("/api/sparql/files").status_code == 404


def test_timeseries(client: TestClient):
    ts = client.get("/api/points/AHU_1_DA_P/timeseries", params={"limit": 10})
    assert ts.status_code == 200
    samples = ts.json()["samples"]
    assert samples
    assert samples == sorted(samples, key=lambda s: s["ts"])
    assert client.get("/api/points/NO_SUCH_POINT/timeseries").status_code == 404


def test_removed_routes(client: TestClient):
    assert client.get("/api/equipment").status_code == 404
    assert client.get("/api/model/ttl").status_code == 404
    assert client.get("/redoc").status_code == 404
