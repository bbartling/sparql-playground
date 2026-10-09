from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings


def test_ui(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    client = TestClient(app)
    html = client.get("/ui")
    assert html.status_code == 200
    assert "SPARQL" in html.text
    js = client.get("/static/app.js")
    assert js.status_code == 200
