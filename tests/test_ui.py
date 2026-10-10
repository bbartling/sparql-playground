from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings


def test_docs_and_bare_surface(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        docs = client.get("/docs")
        assert docs.status_code == 200

        root = client.get("/", follow_redirects=False)
        assert root.status_code in (301, 302, 303, 307, 308)
        assert root.headers.get("location", "").endswith("/docs")

        openapi = client.get("/openapi.json").json()
        paths = set(openapi["paths"])
        assert "/api/sparql" in paths
        assert "/api/sparql/upload" in paths
        assert "/api/sparql/files" in paths
        assert "/api/points/{point_id}/timeseries" in paths
        assert "/health" in paths
        assert "/hello" in paths
        assert "/api/equipment" not in paths
        assert "/api/model/ttl" not in paths
