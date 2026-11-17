from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings


def test_docs_and_bare_surface(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200

        root = client.get("/", follow_redirects=False)
        assert root.status_code in (301, 302, 303, 307, 308)
        assert root.headers.get("location", "").endswith("/docs")

        paths = set(client.get("/openapi.json").json()["paths"])
        assert paths == {
            "/health",
            "/api/sparql",
            "/api/sparql/upload",
            "/api/points/{point_id}/timeseries",
            "/api/model/ttl",
        }
