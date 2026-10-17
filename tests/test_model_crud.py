from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.graph.namespaces import BLDG, REF
from brickts.ingest import bootstrap_all
from brickts.settings import Settings


def test_tree_and_mutations_gate(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        tree = client.get("/api/model/tree")
        assert tree.status_code == 200
        body = tree.json()
        assert body["ok"] is True
        assert body["tree"]
        assert body["allow_mutations"] is False

        denied = client.post(
            "/api/model/equip",
            json={"equipment_id": "AHU_X", "kind": "ahu"},
        )
        assert denied.status_code == 403


def test_crud_preserves_timeseries_refs(settings: Settings):
    settings.allow_mutations = True
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        before = {
            str(s): str(tid)
            for s, _, ref in client.app.state.ctx.graph.state.model.triples(
                (None, REF.hasExternalReference, None)
            )
            for tid in client.app.state.ctx.graph.state.model.objects(ref, REF.hasTimeseriesId)
        }
        # Use graph service directly for the baseline count via API point that exists
        point_iri = str(BLDG.AHU_1_DA_P)
        assert point_iri in before

        tagged = client.post(
            "/api/model/tags",
            json={
                "updates": [
                    {
                        "entity_id": "AHU_1_DA_P",
                        "level": "point",
                        "markers": ["point", "sensor", "temp"],
                    }
                ],
            },
        )
        assert tagged.status_code == 200, tagged.text

        sug = client.get(
            "/api/model/haystack/suggest", params={"q": "discharge air temp", "level": "point"}
        )
        assert sug.status_code == 200
        assert sug.json()["suggestions"]

        renamed = client.post(
            "/api/model/rename",
            json={"entity_id": "AHU_1_DA_P", "label": "AHU-1 Discharge Air Temp"},
        )
        assert renamed.status_code == 200, renamed.text

        after = {
            str(s): str(tid)
            for s, _, ref in client.app.state.ctx.graph.state.model.triples(
                (None, REF.hasExternalReference, None)
            )
            for tid in client.app.state.ctx.graph.state.model.objects(ref, REF.hasTimeseriesId)
        }
        assert after[point_iri] == before[point_iri]

        added = client.post(
            "/api/model/point",
            json={
                "point_id": "AHU_1_Demo_Sensor",
                "owner_id": "AHU_1",
                "brick_class": "Sensor",
                "label": "Demo Sensor",
            },
        )
        assert added.status_code == 200, added.text
        assert added.json()["timeseries_id"]

        hidden = client.post("/api/model/hide", json={"entity_id": "AHU_1_Demo_Sensor"})
        assert hidden.status_code == 200

        flush = client.post("/api/model/flush")
        assert flush.status_code == 200
        assert settings.tutorial_ttl_path.exists()
        text = settings.tutorial_ttl_path.read_text(encoding="utf-8")
        assert "AHU_1_DA_P" in text
        assert before[point_iri] in text


def test_ttl_download_schedules_tutorial_file(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        resp = client.get("/api/model/ttl")
        assert resp.status_code == 200
        assert "AHU_1" in resp.text
        # Background thread may need a beat; flush guarantees the file for beginners.
        client.post("/api/model/flush")
        assert settings.tutorial_ttl_path.exists()
