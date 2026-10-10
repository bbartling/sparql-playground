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
        assert "API JSON" in html.text
        assert "theme-toggle" in html.text
        assert "Open-FDD" not in html.text
        assert "analyst_client" not in html.text
        assert "<select" not in html.text.lower()
        root = client.get("/", follow_redirects=False)
        assert root.status_code in (301, 302, 303, 307, 308)
        assert root.headers.get("location", "").endswith("/ui")
        js = client.get("/static/app.js")
        assert js.status_code == 200
        assert "mech_system_summary" in js.text
        assert "applyTheme" in js.text
        assert "Open-FDD" not in js.text
        assert "loadApplicableRules" not in js.text
        assert "loadFaultLesson" not in js.text
        ttl = client.get("/api/model/ttl")
        assert ttl.status_code == 200
        assert "text/turtle" in ttl.headers.get("content-type", "")
        assert "Air_Handler_Unit" in ttl.text
