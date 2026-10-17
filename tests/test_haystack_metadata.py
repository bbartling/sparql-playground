"""Explicit Haystack values, honest status and mutation-safety regressions."""

import pytest
from bldgts.api.app import create_app
from bldgts.graph.namespaces import BLDG, BRICK, BTS, REF
from bldgts.haystack.metadata import metadata, replace_metadata, validate_entity
from bldgts.ingest import bootstrap_all
from bldgts.settings import Settings
from fastapi.testclient import TestClient
from rdflib import Graph, Literal
from rdflib.namespace import RDF


def tag(kind, value):
    return {"kind": kind, "value": value}


def flatten(nodes):
    return [item for node in nodes for item in [node, *flatten(node.get("children", []))]]


def point(client):
    return next(
        item
        for item in flatten(client.get("/api/model/tree").json()["tree"])
        if item["id"] == "AHU_1_DA_P"
    )


def post_metadata(client, *, kind="Bool", markers=None, extra=None, revision=None):
    values = {
        "kind": tag("Str", kind),
        "siteRef": tag("Ref", "Site"),
        "equipRef": tag("Ref", "AHU_1"),
        **(extra or {}),
    }
    return client.post(
        "/api/model/metadata",
        json={
            "expected_revision": revision,
            "updates": [
                {
                    "entity_id": "AHU_1_DA_P",
                    "metadata": values,
                    "markers": markers if markers is not None else ["point", "sensor"],
                }
            ],
        },
    )


@pytest.fixture
def editor(settings: Settings):
    settings.allow_mutations = True
    bootstrap_all(settings)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/model/metadata",
            json={
                "updates": [
                    {
                        "entity_id": "Site",
                        "markers": ["site"],
                        "metadata": {"tz": tag("Str", "America/Chicago")},
                    },
                    {
                        "entity_id": "AHU_1",
                        "markers": ["equip", "ahu"],
                        "metadata": {"siteRef": tag("Ref", "Site")},
                    },
                ]
            },
        )
        assert response.status_code == 200, response.text
        yield client


def test_seed_hints_never_count_as_authored_metadata(settings: Settings):
    bootstrap_all(settings)
    with TestClient(create_app(settings)) as client:
        nodes = flatten(client.get("/api/model/tree").json()["tree"])
        assert all(n["markers"] == [] and n["metadata"] == {} for n in nodes)
        assert all(n["status"] == "red" for n in nodes)
        assert point(client)["hints"]
        denied = client.post(
            "/api/model/metadata",
            json={
                "updates": [
                    {"entity_id": "Site", "metadata": {"tz": tag("Str", "UTC")}},
                ]
            },
        )
        assert denied.status_code == 403


def test_status_distinguishes_required_errors_and_recommendations(editor):
    assert post_metadata(editor).status_code == 200
    current = point(editor)
    assert current["status"] == "green"
    assert current["complete"] is True
    assert "his" not in current["markers"]  # Historization is a capability, not mandatory.

    assert post_metadata(editor, kind="Number").status_code == 200
    current = point(editor)
    assert current["status"] == "yellow"
    assert current["issues"] == [
        {
            "severity": "warning",
            "tag": "unit",
            "message": "Consider a unit for a numeric point; unitless values are valid.",
        }
    ]

    assert post_metadata(editor, kind="Number", extra={"unit": tag("Str", "°C")}).status_code == 200
    assert point(editor)["status"] == "green"
    assert post_metadata(editor, markers=["point", "sensor", "cmd"]).status_code == 200
    assert point(editor)["status"] == "red"
    assert any(i["tag"] == "function" for i in point(editor)["issues"])


def test_historization_requires_valid_timezone_and_mode(editor):
    assert post_metadata(editor, markers=["point", "sensor", "his"]).status_code == 200
    assert {i["tag"] for i in point(editor)["issues"]} == {"tz", "hisMode"}
    valid = {"tz": tag("Str", "Chicago"), "hisMode": tag("Str", "cov")}
    assert post_metadata(editor, markers=["point", "sensor", "his"], extra=valid).status_code == 200
    assert point(editor)["status"] == "green"
    bad = {"tz": tag("Str", "America/New_York"), "hisMode": tag("Str", "often")}
    assert post_metadata(editor, markers=["point", "sensor", "his"], extra=bad).status_code == 200
    issues = point(editor)["issues"]
    assert {i["tag"] for i in issues} == {"tz", "hisMode"}


@pytest.mark.parametrize(
    "extra,issue_tag",
    [
        ({"siteRef": tag("Ref", "AHU_1")}, "siteRef"),
        ({"equipRef": tag("Ref", "Site")}, "equipRef"),
        ({"equipRef": tag("Ref", "nonexistent")}, "equipRef"),
        ({"kind": tag("Number", 7)}, "kind"),
        ({"tz": tag("Str", "not-a-real-timezone")}, "tz"),
    ],
)
def test_invalid_semantics_save_with_actionable_red_issues(editor, extra, issue_tag):
    assert post_metadata(editor, extra=extra).status_code == 200
    current = point(editor)
    assert current["status"] == "red"
    assert any(i["tag"] == issue_tag and i["severity"] == "error" for i in current["issues"])


def test_metadata_roundtrip_preserves_types_labels_and_timeseries(editor, settings):
    graph = editor.app.state.ctx.graph
    before = list(graph.state.model.objects(BLDG.AHU_1_DA_P, REF.hasExternalReference))
    tid = str(graph.state.model.value(before[0], REF.hasTimeseriesId))
    values = {
        "dis": tag("Str", "Discharge pressure"),
        "curVal": tag("Bool", True),
        "minVal": tag("Number", 0),
        "precision": tag("Number", 2),
    }
    assert post_metadata(editor, extra=values).status_code == 200
    current = point(editor)
    assert current["name"] == "Discharge pressure"
    assert current["id"] == "AHU_1_DA_P"
    assert current["metadata"]["curVal"] == tag("Bool", True)
    assert current["metadata"]["minVal"] == tag("Number", 0)
    assert current["tags"]["timeseries_id"] == tid
    assert list(graph.state.model.objects(BLDG.AHU_1_DA_P, REF.hasExternalReference)) == before
    assert editor.post("/api/model/flush").status_code == 200
    persisted = Graph().parse(settings.tutorial_ttl_path, format="turtle")
    assert metadata(persisted, BLDG.AHU_1_DA_P) == current["metadata"]
    assert (
        editor.post(
            "/api/model/rename",
            json={
                "entity_id": "AHU_1_DA_P",
                "label": "Pressure sensor",
            },
        ).status_code
        == 200
    )
    assert point(editor)["metadata"]["dis"] == tag("Str", "Pressure sensor")


def test_metadata_batch_revision_and_malformed_value_rollback(editor):
    revision = editor.get("/api/model/tree").json()["revision"]
    assert post_metadata(editor, revision=revision).status_code == 200
    before = point(editor)
    conflict = post_metadata(editor, revision=revision)
    assert conflict.status_code == 409
    revision += 1
    failed = editor.post(
        "/api/model/metadata",
        json={
            "expected_revision": revision,
            "updates": [
                {"entity_id": "AHU_1_DA_P", "metadata": {"dis": tag("Str", "Discard me")}},
                {"entity_id": "AHU_1", "metadata": {"minVal": tag("Number", True)}},
            ],
        },
    )
    assert failed.status_code == 400
    assert editor.get("/api/model/tree").json()["revision"] == revision
    assert point(editor) == before
    for invalid in (
        {"equipRef": tag("Ref", "AHU 1")},
        {"customRef": tag("Ref", "https://example.com/<bad>")},
        {"minVal": tag("Number", 10**400)},
    ):
        response = editor.post(
            "/api/model/metadata",
            json={
                "expected_revision": revision,
                "updates": [{"entity_id": "AHU_1_DA_P", "metadata": invalid}],
            },
        )
        assert response.status_code == 400, response.text
        assert editor.get("/api/model/tree").json()["revision"] == revision
        assert point(editor) == before


@pytest.mark.parametrize(
    "entity,level,markers",
    [
        ("nonexistent", "point", ["point"]),
        ("Site", "point", ["point", "sensor"]),
        ("AHU_1_DA_P", "equip", ["equip", "ahu"]),
        ("AHU_1_DA_P", "point", ["unit"]),
    ],
)
def test_marker_endpoint_rejects_unknown_entities_spoofed_levels_and_value_tags(
    editor,
    entity,
    level,
    markers,
):
    revision = editor.get("/api/model/tree").json()["revision"]
    response = editor.post(
        "/api/model/tags",
        json={
            "updates": [
                {"entity_id": entity, "level": level, "markers": markers},
            ]
        },
    )
    assert response.status_code == 400
    assert editor.get("/api/model/tree").json()["revision"] == revision


def core_graph():
    graph = Graph()
    for entity, cls, markers in (
        (BLDG.Site, BRICK.Site, ["site"]),
        (BLDG.OtherSite, BRICK.Site, ["site"]),
        (BLDG.AHU_1, BRICK.Air_Handler_Unit, ["equip", "ahu"]),
        (BLDG.Fan, BRICK.Fan, ["equip", "fan"]),
        (BLDG.Point, BRICK.Point, ["point", "sensor"]),
    ):
        graph.add((entity, RDF.type, cls))
        for marker in markers:
            graph.add((entity, BTS.hasHaystackMarker, Literal(marker)))
    replace_metadata(graph, BLDG.Site, {"tz": tag("Str", "America/Chicago")})
    replace_metadata(graph, BLDG.AHU_1, {"siteRef": tag("Ref", "Site")})
    replace_metadata(
        graph,
        BLDG.Point,
        {
            "kind": tag("Str", "Number"),
            "siteRef": tag("Ref", "Site"),
            "equipRef": tag("Ref", "AHU_1"),
            "unit": tag("Str", "Pa"),
        },
    )
    return graph


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"unit": tag("Str", "bananas")}, "unit"),
        ({"minVal": tag("Number", 5), "maxVal": tag("Number", 2)}, "minVal"),
        ({"kind": tag("Str", "Bool"), "minVal": tag("Number", 0)}, "minVal"),
        ({"kind": tag("Str", "Bool"), "enum": tag("Str", "off,on,unknown")}, "enum"),
        ({"kind": tag("Str", "Str"), "enum": tag("Str", "off,off")}, "enum"),
        ({"kind": tag("Str", "Str"), "enum": tag("Str", "off,,on")}, "enum"),
    ],
)
def test_units_bounds_and_enum_hygiene(changes, expected):
    graph = core_graph()
    replace_metadata(graph, BLDG.Point, {**metadata(graph, BLDG.Point), **changes})
    report = validate_entity(graph, BLDG.Point)
    assert report["status"] == "red"
    assert any(i["tag"] == expected for i in report["issues"])


def test_reference_site_consistency_and_equipment_containment_cycle():
    graph = core_graph()
    values = metadata(graph, BLDG.Point)
    values["siteRef"] = tag("Ref", "OtherSite")
    replace_metadata(graph, BLDG.Point, values)
    report = validate_entity(graph, BLDG.Point)
    assert any("same site" in i["message"] for i in report["issues"])
    replace_metadata(
        graph,
        BLDG.AHU_1,
        {
            "siteRef": tag("Ref", "Site"),
            "equipRef": tag("Ref", "Fan"),
        },
    )
    replace_metadata(
        graph,
        BLDG.Fan,
        {
            "siteRef": tag("Ref", "Site"),
            "equipRef": tag("Ref", "AHU_1"),
        },
    )
    report = validate_entity(graph, BLDG.AHU_1)
    assert any("cycle" in i["message"] for i in report["issues"])


def test_taxonomy_descendants_and_legacy_fabricated_marker_are_validated():
    graph = core_graph()
    graph.remove((BLDG.Point, BTS.hasHaystackMarker, Literal("sensor")))
    for marker in ("synthetic", "computed"):
        graph.add((BLDG.Point, BTS.hasHaystackMarker, Literal(marker)))
    assert validate_entity(graph, BLDG.Point)["status"] == "green"
    graph.add((BLDG.Point, BTS.hasHaystackMarker, Literal("status")))
    assert validate_entity(graph, BLDG.Point)["status"] == "red"
    with pytest.raises(ValueError, match="is a marker"):
        replace_metadata(graph, BLDG.Point, {"hisTotalized": tag("Bool", True)})


def test_rename_invalid_input_is_400_and_all_levels_keep_stable_ids(editor):
    for entity in ("Site", "Building_50", "AHU_1", "AHU_1_DA_P"):
        response = editor.post(
            "/api/model/rename",
            json={
                "entity_id": entity,
                "label": f"Renamed {entity}",
            },
        )
        assert response.status_code == 200
        node = next(
            n for n in flatten(editor.get("/api/model/tree").json()["tree"]) if n["id"] == entity
        )
        assert node["name"] == f"Renamed {entity}"
    response = editor.post(
        "/api/model/rename",
        json={
            "entity_id": "AHU_1",
            "label": "   ",
        },
    )
    assert response.status_code == 400


def test_explicit_equipment_ref_moves_point_in_tree_and_sparql_without_changing_timeseries(editor):
    graph = editor.app.state.ctx.graph
    before = list(graph.state.model.objects(BLDG.AHU_1_DA_P, REF.hasExternalReference))
    tid = str(graph.state.model.value(before[0], REF.hasTimeseriesId))
    assert post_metadata(editor, extra={"equipRef": tag("Ref", "AHU_2")}).status_code == 200
    model = graph.state.model
    assert list(model.objects(BLDG.AHU_1_DA_P, BRICK.isPointOf)) == [BLDG.AHU_2]
    assert (BLDG.AHU_2, BRICK.hasPoint, BLDG.AHU_1_DA_P) in model
    assert (BLDG.AHU_1, BRICK.hasPoint, BLDG.AHU_1_DA_P) not in model
    nodes = flatten(editor.get("/api/model/tree").json()["tree"])
    owner = next(n for n in nodes if n["id"] == "AHU_2")
    assert "AHU_1_DA_P" in {n["id"] for n in flatten(owner["children"])}
    assert list(model.objects(BLDG.AHU_1_DA_P, REF.hasExternalReference)) == before
    assert str(model.value(before[0], REF.hasTimeseriesId)) == tid
    query = """PREFIX brick: <https://brickschema.org/schema/Brick#>
    SELECT ?owner WHERE {
      <https://example.com/bldg#AHU_1_DA_P> brick:isPointOf ?owner
    }"""
    # Use the model namespace directly; this assertion checks the same graph
    # clients query, independently of the frontend tree construction.
    query = query.replace("https://example.com/bldg#AHU_1_DA_P", str(BLDG.AHU_1_DA_P))
    assert [row.owner for row in graph.state.union.query(query)] == [BLDG.AHU_2]

    assert (
        post_metadata(editor, extra={"equipRef": tag("Ref", "not-yet-imported")}).status_code == 200
    )
    assert point(editor)["status"] == "red"
    assert list(graph.state.model.objects(BLDG.AHU_1_DA_P, BRICK.isPointOf)) == [BLDG.AHU_2]
