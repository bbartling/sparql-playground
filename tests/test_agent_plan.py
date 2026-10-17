"""Acceptance tests for the SPARQL agent plan/apply contract (A19)."""

from __future__ import annotations

import pytest
from bldgts.api.app import create_app
from bldgts.ingest import bootstrap_all
from bldgts.settings import Settings
from fastapi.testclient import TestClient

PREFIX = """
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX bts: <https://example.org/openfdd/bldgts#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
"""


@pytest.fixture()
def client(settings: Settings):
    bootstrap_all(settings)
    settings.allow_mutations = True
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def _point_id(client: TestClient) -> tuple[str, str, int]:
    tree = client.get("/api/model/tree").json()
    revision = tree["revision"]

    def walk(nodes):
        for node in nodes:
            if node["node_type"] == "point":
                return node
            found = walk(node.get("children") or [])
            if found:
                return found
        return None

    point = walk(tree["tree"])
    assert point, "expected at least one point"
    return point["id"], point["tags"].get("timeseries_id", ""), revision


def test_sparql_remains_read_only(client: TestClient):
    resp = client.post(
        "/api/sparql",
        json={"query": "INSERT DATA { <urn:x> <urn:y> <urn:z> }"},
    )
    assert resp.status_code == 400
    assert "not allowed" in resp.text.lower() or "update" in resp.text.lower()


def test_discovery_select_returns_typed_terms(client: TestClient):
    point_id, _, _ = _point_id(client)
    query = f"""
    PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
    PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?point ?label ?ref WHERE {{
      BIND(bldg:{point_id} AS ?point)
      OPTIONAL {{ ?point rdfs:label ?label }}
      OPTIONAL {{ ?point ref:hasExternalReference ?ref }}
    }}
    """
    resp = client.post("/api/sparql", json={"query": query})
    assert resp.status_code == 200
    body = resp.json()
    bindings = body["results"]["results"]["bindings"]
    assert bindings
    row = bindings[0]
    assert row["point"]["type"] == "uri"
    if "ref" in row:
        # TimeseriesReference nodes may be blank nodes in the seed graph.
        assert row["ref"]["type"] in {"uri", "bnode"}
    if "label" in row:
        assert row["label"]["type"] == "literal"


def test_plan_rejects_disallowed_and_protected(client: TestClient):
    point_id, _, revision = _point_id(client)
    # WHERE / DELETE form
    bad = client.post(
        "/api/agent/plan",
        json={
            "update": f"{PREFIX}\nDELETE {{ ?s ?p ?o }} WHERE {{ ?s ?p ?o }}",
            "scope_iris": [point_id],
            "expected_revision": revision,
        },
    )
    assert bad.status_code == 400

    protected = client.post(
        "/api/agent/plan",
        json={
            "update": f"""{PREFIX}
INSERT DATA {{ bldg:{point_id} ref:hasTimeseriesId "nope" . }}
""",
            "scope_iris": [point_id],
            "expected_revision": revision,
        },
    )
    assert protected.status_code == 400
    assert (
        "protected" in protected.text.lower()
        or "allowlisted" in protected.text.lower()
        or "not allowlisted" in protected.text.lower()
    )


def test_plan_rejects_scope_expansion_and_service(client: TestClient):
    point_id, _, revision = _point_id(client)
    outside = client.post(
        "/api/agent/plan",
        json={
            "update": f"""{PREFIX}
INSERT DATA {{ bldg:AHU_1 rdfs:label "sneaky" . }}
""",
            "scope_iris": [point_id],
            "expected_revision": revision,
        },
    )
    assert outside.status_code == 400

    service = client.post(
        "/api/agent/plan",
        json={
            "update": f"""{PREFIX}
INSERT DATA {{ bldg:{point_id} rdfs:label "x" . }}
SERVICE <http://example.org/sparql> {{ }}
""",
            "scope_iris": [point_id],
            "expected_revision": revision,
        },
    )
    assert service.status_code == 400


def test_plan_apply_preserves_timeseries_and_refreshes(client: TestClient):
    point_id, timeseries_id, revision = _point_id(client)
    update = f"""{PREFIX}
DELETE DATA {{
  bldg:{point_id} bts:hasHaystackMarker "sensor" .
}}
;
INSERT DATA {{
  bldg:{point_id} rdfs:label "Agent tagged point" .
  bldg:{point_id} bts:hasHaystackMarker "point" .
  bldg:{point_id} bts:hasHaystackMarker "sensor" .
  bldg:{point_id} bts:hasHaystackMarker "discharge" .
  bldg:{point_id} bts:hasHaystackTag _:k .
  _:k bts:tagName "kind" ; bts:tagKind "Str" ; bts:tagValue "Number" .
  bldg:{point_id} bts:hasHaystackTag _:s .
  _:s bts:tagName "siteRef" ; bts:tagKind "Ref" ; bts:tagValue bldg:Building_50 .
  bldg:{point_id} bts:hasHaystackTag _:e .
  _:e bts:tagName "equipRef" ; bts:tagKind "Ref" ; bts:tagValue bldg:AHU_1 .
}}
"""
    planned = client.post(
        "/api/agent/plan",
        json={"update": update, "scope_iris": [point_id], "expected_revision": revision},
    )
    assert planned.status_code == 200, planned.text
    plan = planned.json()
    assert plan["plan_id"] and plan["plan_hash"]
    assert any(point_id in iri for iri in plan["affected_iris"])

    applied = client.post(
        "/api/agent/apply",
        json={
            "plan_id": plan["plan_id"],
            "plan_hash": plan["plan_hash"],
            "expected_revision": revision,
        },
    )
    assert applied.status_code == 200, applied.text
    new_rev = applied.json()["revision"]
    assert new_rev > revision

    tree = client.get("/api/model/tree").json()["tree"]

    def find(nodes):
        for node in nodes:
            if node["id"] == point_id:
                return node
            found = find(node.get("children") or [])
            if found:
                return found
        return None

    point = find(tree)
    assert point
    assert point["name"] == "Agent tagged point"
    assert "point" in point["markers"]
    assert "sensor" in point["markers"]
    assert "discharge" in point["markers"]
    assert point["metadata"]["kind"]["value"] == "Number"
    assert point["tags"].get("timeseries_id") == timeseries_id

    # Replay rejected.
    replay = client.post(
        "/api/agent/apply",
        json={
            "plan_id": plan["plan_id"],
            "plan_hash": plan["plan_hash"],
            "expected_revision": new_rev,
        },
    )
    assert replay.status_code == 400


def test_plan_tamper_hash_and_stale_revision(client: TestClient):
    point_id, _, revision = _point_id(client)
    update = f"""{PREFIX}
INSERT DATA {{ bldg:{point_id} rdfs:label "Tamper check" . }}
"""
    planned = client.post(
        "/api/agent/plan",
        json={"update": update, "scope_iris": [point_id], "expected_revision": revision},
    ).json()
    bad_hash = client.post(
        "/api/agent/apply",
        json={
            "plan_id": planned["plan_id"],
            "plan_hash": "0" * 64,
            "expected_revision": revision,
        },
    )
    assert bad_hash.status_code == 400

    # Stale revision after an intervening rename via UI path.
    rename = client.post(
        "/api/model/rename",
        json={"entity_id": point_id, "label": "Intervening edit", "expected_revision": revision},
    )
    assert rename.status_code == 200
    stale = client.post(
        "/api/agent/apply",
        json={
            "plan_id": planned["plan_id"],
            "plan_hash": planned["plan_hash"],
            "expected_revision": revision,
        },
    )
    assert stale.status_code == 409


def test_mutations_disabled_blocks_apply(settings: Settings):
    bootstrap_all(settings)
    settings.allow_mutations = False
    app = create_app(settings)
    with TestClient(app) as client:
        point_id, _, revision = _point_id(client)
        # Planning is read-side preview and remains available.
        settings.allow_mutations = True  # temporarily for plan create via settings already frozen
    # Recreate with mutations on for plan, then apply with mutations off.
    settings.allow_mutations = True
    app2 = create_app(settings)
    with TestClient(app2) as client:
        point_id, _, revision = _point_id(client)
        planned = client.post(
            "/api/agent/plan",
            json={
                "update": f'{PREFIX}\nINSERT DATA {{ bldg:{point_id} rdfs:label "x" . }}',
                "scope_iris": [point_id],
                "expected_revision": revision,
            },
        ).json()
    settings.allow_mutations = False
    app3 = create_app(settings)
    # Plan store is process-global — same interpreter retains the plan.
    with TestClient(app3) as client:
        blocked = client.post(
            "/api/agent/apply",
            json={
                "plan_id": planned["plan_id"],
                "plan_hash": planned["plan_hash"],
                "expected_revision": planned["base_revision"],
            },
        )
        assert blocked.status_code == 403


def test_build_plan_preserves_unedited_metadata(settings: Settings):
    bootstrap_all(settings)
    settings.allow_mutations = True
    app = create_app(settings)
    with TestClient(app) as client:
        point_id, _, revision = _point_id(client)
        # Seed kind + equipRef via UI metadata path.
        seed = client.post(
            "/api/model/metadata",
            json={
                "expected_revision": revision,
                "updates": [
                    {
                        "entity_id": point_id,
                        "markers": ["point", "sensor"],
                        "metadata": {
                            "kind": {"kind": "Str", "value": "Number"},
                            "unit": {"kind": "Str", "value": "kPa"},
                            "siteRef": {"kind": "Ref", "value": "Building_50"},
                            "equipRef": {"kind": "Ref", "value": "AHU_1"},
                        },
                    }
                ],
            },
        )
        assert seed.status_code == 200, seed.text
        revision = seed.json()["revision"]
        # Agent only replaces kind; unit must remain.
        update = f"""{PREFIX}
INSERT DATA {{
  bldg:{point_id} bts:hasHaystackTag _:k .
  _:k bts:tagName "kind" ; bts:tagKind "Str" ; bts:tagValue "Bool" .
}}
"""
        planned = client.post(
            "/api/agent/plan",
            json={"update": update, "scope_iris": [point_id], "expected_revision": revision},
        )
        assert planned.status_code == 200, planned.text
        meta = planned.json()["entity_changes"]
        # entity_changes keys are full IRIs
        values = next(iter(meta.values()))["metadata"]
        assert values["kind"]["value"] == "Bool"
        assert values["unit"]["value"] == "kPa"


def test_malformed_metadata_rolls_back(client: TestClient):
    point_id, timeseries_id, revision = _point_id(client)
    before = client.get("/api/model/tree").json()["revision"]
    update = f"""{PREFIX}
INSERT DATA {{
  bldg:{point_id} bts:hasHaystackTag _:k .
  _:k bts:tagName "kind" ; bts:tagKind "Nope" ; bts:tagValue "Number" .
}}
"""
    # Unsupported tagKind fails at plan dry-run (replace_metadata) before commit.
    planned = client.post(
        "/api/agent/plan",
        json={"update": update, "scope_iris": [point_id], "expected_revision": revision},
    )
    assert planned.status_code == 400
    after = client.get("/api/model/tree").json()
    assert after["revision"] == before

    def find(nodes):
        for node in nodes:
            if node["id"] == point_id:
                return node
            found = find(node.get("children") or [])
            if found:
                return found
        return None

    point = find(after["tree"])
    assert point["tags"].get("timeseries_id") == timeseries_id
