"""The editor must expose the complete Haystack model without duplicating or hiding rows."""

from collections import Counter
from types import SimpleNamespace

from bldgts.graph.namespaces import BLDG, BTS, REF
from bldgts.haystack.defs import catalog_for_level
from bldgts.haystack.metadata import validate_entity
from bldgts.haystack.rdf import add_markers, add_tag, declare_entity
from bldgts.haystack.suggest import guess_marker_bundle
from bldgts.services.model_crud import build_tree
from rdflib import Graph, Literal
from rdflib.namespace import RDFS, XSD


def flatten(nodes):
    return [item for node in nodes for item in [node, *flatten(node["children"])]]


def tree(model):
    service = SimpleNamespace(state=SimpleNamespace(model=model), ontology=Graph())
    return build_tree(service)


def test_full_seed_exposes_every_point_floor_and_space_once(project_root):
    model = Graph().parse(project_root / "model/building_50.ttl", format="turtle")
    nodes = flatten(tree(model))
    counts = Counter(n["iri"] for n in nodes)
    expected = {str(p) for p in model.subjects(REF.hasExternalReference, None)}
    shown = {n["iri"] for n in nodes if n["node_type"] == "point"}
    assert shown == expected
    assert all(count == 1 for count in counts.values())
    floors = {
        str(s)
        for s, _, o in model.triples((None, BTS.hasHaystackMarker, Literal("floor")))
    }
    assert {n["iri"] for n in nodes if n["node_type"] == "floor"} == floors
    spaces = {
        str(s)
        for s, _, o in model.triples((None, BTS.hasHaystackMarker, Literal("space")))
        if (s, BTS.hasHaystackMarker, Literal("floor")) not in model
    }
    assert spaces <= {n["iri"] for n in nodes if n["node_type"] == "space"}
    assert sum(n["points_total"] for n in tree(model)) == len(expected)


def test_haystack_refs_nest_equipment_parts_and_spaces():
    model = Graph()
    declare_entity(model, BLDG.Building_50)
    add_markers(model, BLDG.Building_50, ["site"])
    model.add((BLDG.Building_50, RDFS.label, Literal("Site")))

    declare_entity(model, BLDG.Floor)
    add_markers(model, BLDG.Floor, ["space", "floor"])
    add_tag(model, BLDG.Floor, "siteRef", "Ref", "Building_50")

    declare_entity(model, BLDG.Unit)
    add_markers(model, BLDG.Unit, ["equip", "ahu"])
    add_tag(model, BLDG.Unit, "siteRef", "Ref", "Building_50")

    declare_entity(model, BLDG.Component)
    add_markers(model, BLDG.Component, ["equip", "fan"])
    add_tag(model, BLDG.Component, "siteRef", "Ref", "Building_50")
    add_tag(model, BLDG.Component, "equipRef", "Ref", "Unit")

    declare_entity(model, BLDG.NestedComponent)
    add_markers(model, BLDG.NestedComponent, ["equip", "fan"])
    add_tag(model, BLDG.NestedComponent, "siteRef", "Ref", "Building_50")
    add_tag(model, BLDG.NestedComponent, "equipRef", "Ref", "Component")

    declare_entity(model, BLDG.Room)
    add_markers(model, BLDG.Room, ["space"])
    add_tag(model, BLDG.Room, "siteRef", "Ref", "Building_50")
    add_tag(model, BLDG.Room, "spaceRef", "Ref", "Floor")

    declare_entity(model, BLDG.Point)
    add_markers(model, BLDG.Point, ["point", "sensor", "his"])
    add_tag(model, BLDG.Point, "kind", "Str", "Number")
    add_tag(model, BLDG.Point, "siteRef", "Ref", "Building_50")
    add_tag(model, BLDG.Point, "equipRef", "Ref", "NestedComponent")
    model.add((BLDG.Point, REF.hasExternalReference, BLDG.PointRef))

    nodes = {n["id"]: n for n in flatten(tree(model))}
    assert nodes["Unit"]["node_type"] == "equipment"
    assert nodes["Component"]["node_type"] == "part"
    assert nodes["NestedComponent"]["node_type"] == "part"
    assert nodes["Room"]["node_type"] == "space"
    assert nodes["NestedComponent"]["children"][0]["id"] == "Point"
    assert {n["id"] for n in nodes["Floor"]["children"]} == {"Room"}


def test_cycles_multiple_parents_and_hidden_owners_cannot_drop_visible_points():
    model = Graph()
    for entity, markers in (
        (BLDG.A, ["equip", "ahu"]),
        (BLDG.B, ["equip", "ahu"]),
        (BLDG.HiddenOwner, ["equip", "ahu"]),
        (BLDG.Point, ["point", "sensor", "his"]),
        (BLDG.DetachedPoint, ["point", "sensor", "his"]),
        (BLDG.HiddenOwnerPoint, ["point", "sensor", "his"]),
    ):
        declare_entity(model, entity)
        add_markers(model, entity, markers)
    add_tag(model, BLDG.A, "equipRef", "Ref", "B")
    add_tag(model, BLDG.B, "equipRef", "Ref", "A")
    add_tag(model, BLDG.Point, "equipRef", "Ref", "B")
    add_tag(model, BLDG.HiddenOwnerPoint, "equipRef", "Ref", "HiddenOwner")
    model.add((BLDG.HiddenOwner, BTS.hidden, Literal(True, datatype=XSD.boolean)))
    for point in (BLDG.Point, BLDG.DetachedPoint, BLDG.HiddenOwnerPoint):
        model.add((point, REF.hasExternalReference, BLDG[f"{point}Ref"]))
    nodes = flatten(tree(model))
    assert len(nodes) == len({n["iri"] for n in nodes})
    assert {n["id"] for n in nodes if n["node_type"] == "point"} == {
        "Point",
        "DetachedPoint",
        "HiddenOwnerPoint",
    }
    assert "HiddenOwner" not in {n["id"] for n in nodes}


def test_spaces_have_their_own_marker_context_and_are_valid_space_refs():
    assert "space" in catalog_for_level("space")
    assert "floor" in catalog_for_level("floor")
    model = Graph()
    declare_entity(model, BLDG.Building_50)
    add_markers(model, BLDG.Building_50, ["site"])
    declare_entity(model, BLDG.Room)
    add_markers(model, BLDG.Room, ["space"])
    add_tag(model, BLDG.Room, "siteRef", "Ref", "Building_50")
    issues = validate_entity(model, BLDG.Room, "space")
    assert issues["status"] in {"green", "yellow"}
    assert guess_marker_bundle("zone air temp", "point")
