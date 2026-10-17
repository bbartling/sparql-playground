"""RDF CRUD legitimacy without the Vite UI — template for future app bases."""

from __future__ import annotations

from bldgts.settings import Settings
from rdf_crud import (
    api_client,
    assert_markers,
    assert_timeseries_intact,
    guess_markers,
    label_of,
    post_markers,
    timeseries_id_of,
)


def test_guess_then_crud_writes_markers_into_rdf(settings: Settings):
    with api_client(settings) as client:
        tid_before = timeseries_id_of(client, "AHU_1_DA_P")
        assert tid_before

        markers = guess_markers(client, "AHU_1 Discharge Air Temp", "point")
        assert "point" in markers and "temp" in markers

        post_markers(client, entity_id="AHU_1_DA_P", markers=markers, level="point")

        assert_markers(client, "AHU_1_DA_P", set(markers))
        assert_timeseries_intact(client, "AHU_1_DA_P", tid_before)


def test_rename_crud_updates_rdfs_label(settings: Settings):
    with api_client(settings) as client:
        resp = client.post(
            "/api/model/rename",
            json={"entity_id": "AHU_1_DA_P", "label": "Discharge Air Temperature"},
        )
        assert resp.status_code == 200, resp.text
        assert label_of(client, "AHU_1_DA_P") == "Discharge Air Temperature"


def test_mutations_gate_blocks_rdf_writes(settings: Settings):
    with api_client(settings, allow_mutations=False) as client:
        denied = client.post(
            "/api/model/tags",
            json={
                "updates": [
                    {
                        "entity_id": "AHU_1_DA_P",
                        "markers": ["point", "sensor"],
                        "level": "point",
                    }
                ]
            },
        )
        assert denied.status_code == 403
