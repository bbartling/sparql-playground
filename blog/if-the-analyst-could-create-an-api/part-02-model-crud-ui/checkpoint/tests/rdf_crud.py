"""Reusable helpers for RDF CRUD checks — no Vite / browser required.

Pattern for future app-base checkpoints:
1. Build a FastAPI app with ``create_app(settings)`` and ``TestClient``.
2. POST mutations (tags / rename / equip / point).
3. Assert triples on ``client.app.state.ctx.graph.state.model`` (or SPARQL ASK).

Copy this module into a later ``checkpoint/tests/`` or keep importing from repo-root
``tests/rdf_crud.py`` while the live package is ``bldgts``.
"""

from __future__ import annotations

from typing import Any

from bldgts.api.app import create_app
from bldgts.graph.namespaces import BLDG, BTS, REF
from bldgts.ingest import bootstrap_all
from bldgts.settings import Settings
from fastapi.testclient import TestClient
from rdflib import URIRef
from rdflib.namespace import RDFS


def api_client(settings: Settings, *, allow_mutations: bool = True) -> TestClient:
    """In-process HTTP client against the live app (no uvicorn, no web UI)."""
    settings.allow_mutations = allow_mutations
    bootstrap_all(settings)
    return TestClient(create_app(settings))


def graph_model(client: TestClient):
    return client.app.state.ctx.graph.state.model


def entity(local_id: str) -> URIRef:
    return BLDG[local_id]


def markers_on(client: TestClient, local_id: str) -> set[str]:
    g = graph_model(client)
    return {str(o) for o in g.objects(entity(local_id), BTS.hasHaystackMarker)}


def label_of(client: TestClient, local_id: str) -> str | None:
    g = graph_model(client)
    for o in g.objects(entity(local_id), RDFS.label):
        return str(o)
    return None


def timeseries_id_of(client: TestClient, local_id: str) -> str | None:
    g = graph_model(client)
    point = entity(local_id)
    for ref in g.objects(point, REF.hasExternalReference):
        for tid in g.objects(ref, REF.hasTimeseriesId):
            return str(tid)
    return None


def assert_markers(client: TestClient, local_id: str, expected: set[str]) -> None:
    got = markers_on(client, local_id)
    missing = expected - got
    assert not missing, f"{local_id}: missing markers {missing}; have {got}"


def assert_timeseries_intact(client: TestClient, local_id: str, expected_tid: str) -> None:
    got = timeseries_id_of(client, local_id)
    assert got == expected_tid, f"{local_id}: timeseries_id changed {expected_tid!r} → {got!r}"


def post_markers(
    client: TestClient,
    *,
    entity_id: str,
    markers: list[str],
    level: str = "point",
    expected_revision: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "updates": [{"entity_id": entity_id, "markers": markers, "level": level}],
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    resp = client.post("/api/model/tags", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def guess_markers(client: TestClient, name: str, level: str = "point") -> list[str]:
    resp = client.get("/api/model/haystack/guess", params={"q": name, "level": level})
    assert resp.status_code == 200, resp.text
    markers = resp.json()["markers"]
    assert markers, f"empty guess for {name!r}"
    return list(markers)
