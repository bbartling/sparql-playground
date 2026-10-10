from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings


def test_docs_is_the_ui(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        docs = client.get("/docs")
        assert docs.status_code == 200
        assert "swagger" in docs.text.lower() or "openapi" in docs.text.lower()

        root = client.get("/", follow_redirects=False)
        assert root.status_code in (301, 302, 303, 307, 308)
        assert root.headers.get("location", "").endswith("/docs")

        ui = client.get("/ui", follow_redirects=False)
        assert ui.status_code in (301, 302, 303, 307, 308)
        assert ui.headers.get("location", "").endswith("/docs")

        # Old static UI is gone
        assert client.get("/static/app.js").status_code == 404
        assert client.get("/static/index.html").status_code == 404

        ttl = client.get("/api/model/ttl")
        assert ttl.status_code == 200
        assert "text/turtle" in ttl.headers.get("content-type", "")
        assert "Air_Handler_Unit" in ttl.text

        examples = client.get("/api/sparql/examples")
        assert examples.status_code == 200
        assert any(e["id"] == "mech_system_summary" for e in examples.json()["examples"])
