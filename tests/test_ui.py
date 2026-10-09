from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings


def test_ui(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        html = client.get("/ui")
        assert html.status_code == 200
        assert "SPARQL" in html.text
        assert "View RDF model" in html.text
        js = client.get("/static/app.js")
        assert js.status_code == 200
        ttl = client.get("/api/model/ttl")
        assert ttl.status_code == 200
        assert "text/turtle" in ttl.headers.get("content-type", "")
        assert "Air_Handler_Unit" in ttl.text
