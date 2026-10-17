"""The editor must expose the complete model without duplicating or hiding rows."""

from collections import Counter
from types import SimpleNamespace

from bldgts.graph.namespaces import BLDG, BRICK, BTS, REF
from bldgts.graph.ontology import load_brick_ontology
from bldgts.haystack.defs import catalog_for_level
from bldgts.haystack.metadata import entity_level, replace_metadata, validate_entity
from bldgts.haystack.suggest import guess_marker_bundle
from bldgts.services.model_crud import build_tree
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, RDFS, XSD


def flatten(nodes):
    return [item for node in nodes for item in [node, *flatten(node["children"])]]


def tree(model):
    service = SimpleNamespace(state=SimpleNamespace(model=model), ontology=load_brick_ontology())
    return build_tree(service)


def test_full_seed_exposes_every_point_floor_and_space_once(project_root):
    model = Graph().parse(project_root / "model/building_50.ttl", format="turtle")
    nodes = flatten(tree(model))
    counts = Counter(n["iri"] for n in nodes)
    expected = {str(p) for p in model.subjects(REF.hasExternalReference, None)}
    shown = {n["iri"] for n in nodes if n["node_type"] == "point"}
    assert shown == expected
    assert all(count == 1 for count in counts.values())
    assert {n["iri"] for n in nodes if n["node_type"] == "floor"} == {
        str(f) for f in model.subjects(RDF.type, BRICK.Floor)
    }
    assert {str(z) for z in model.subjects(RDF.type, BRICK.HVAC_Zone)} <= {
        n["iri"] for n in nodes if n["node_type"] == "space"
    }
    assert sum(n["points_total"] for n in tree(model)) == len(expected)


def test_inverse_location_edges_nested_parts_and_custom_subclasses_are_discovered():
    model = Graph()
    custom = Namespace("urn:custom:")
    model.add((custom.RoofUnit, RDFS.subClassOf, BRICK.Equipment))
    for entity, cls in (
        (BLDG.Site, BRICK.Site),
        (BLDG.Building, BRICK.Building),
        (BLDG.Floor, BRICK.Floor),
        (BLDG.Unit, custom.RoofUnit),
        (BLDG.Component, BRICK.Fan),
        (BLDG.NestedComponent, BRICK.Motor),
        (BLDG.Room, BRICK.HVAC_Zone),
        (BLDG.Point, BRICK.Sensor),
    ):
        model.add((entity, RDF.type, cls))
    # Mix forward-only, inverse-only and redundant relationships.
    model.add((BLDG.Building, BRICK.isPartOf, BLDG.Site))
    model.add((BLDG.Building, BRICK.hasPart, BLDG.Floor))
    model.add((BLDG.Floor, BRICK.isPartOf, BLDG.Building))
    model.add((BLDG.Unit, BRICK.isLocatedIn, BLDG.Floor))
    model.add((BLDG.Component, BRICK.isPartOf, BLDG.Unit))
    model.add((BLDG.NestedComponent, BRICK.isPartOf, BLDG.Component))
    model.add((BLDG.Room, BRICK.isPartOf, BLDG.Floor))
    model.add((BLDG.NestedComponent, BRICK.hasPoint, BLDG.Point))
    nodes = {n["id"]: n for n in flatten(tree(model))}
    assert nodes["Unit"]["node_type"] == "equipment"
    assert nodes["Component"]["node_type"] == "part"
    assert nodes["NestedComponent"]["node_type"] == "part"
    assert nodes["Room"]["node_type"] == "space"
    assert nodes["NestedComponent"]["children"][0]["id"] == "Point"
    assert {n["id"] for n in nodes["Floor"]["children"]} == {"Unit", "Room"}


def test_cycles_multiple_parents_and_hidden_owners_cannot_drop_visible_points():
    model = Graph()
    for entity, cls in (
        (BLDG.A, BRICK.Equipment),
        (BLDG.B, BRICK.Equipment),
        (BLDG.HiddenOwner, BRICK.Equipment),
        (BLDG.Point, BRICK.Point),
        (BLDG.DetachedPoint, BRICK.Point),
        (BLDG.HiddenOwnerPoint, BRICK.Point),
    ):
        model.add((entity, RDF.type, cls))
    model.add((BLDG.A, BRICK.isPartOf, BLDG.B))
    model.add((BLDG.B, BRICK.isPartOf, BLDG.A))
    model.add((BLDG.Point, BRICK.isPointOf, BLDG.B))
    model.add((BLDG.A, BRICK.hasPoint, BLDG.Point))
    model.add((BLDG.HiddenOwner, BTS.hidden, Literal(True, datatype=XSD.boolean)))
    model.add((BLDG.HiddenOwnerPoint, BRICK.isPointOf, BLDG.HiddenOwner))
    nodes = flatten(tree(model))
    assert len(nodes) == len({n["iri"] for n in nodes})
    assert {n["id"] for n in nodes if n["node_type"] == "point"} == {
        "Point",
        "DetachedPoint",
        "HiddenOwnerPoint",
    }
    assert "HiddenOwner" not in {n["id"] for n in nodes}


def test_spaces_have_their_own_marker_context_and_are_valid_space_refs():
    model = Graph()
    for entity, cls, marker in (
        (BLDG.Site, BRICK.Site, "site"),
        (BLDG.Unit, BRICK.Equipment, "equip"),
        (BLDG.Room, BRICK.HVAC_Zone, "space"),
        (BLDG.Point, BRICK.Sensor, "point"),
    ):
        model.add((entity, RDF.type, cls))
        model.add((entity, BTS.hasHaystackMarker, Literal(marker)))
    model.add((BLDG.Point, BTS.hasHaystackMarker, Literal("sensor")))
    replace_metadata(model, BLDG.Unit, {"siteRef": {"kind": "Ref", "value": "Site"}})
    replace_metadata(
        model,
        BLDG.Point,
        {
            "kind": {"kind": "Str", "value": "Bool"},
            "siteRef": {"kind": "Ref", "value": "Site"},
            "equipRef": {"kind": "Ref", "value": "Unit"},
            "spaceRef": {"kind": "Ref", "value": "Room"},
        },
    )
    assert entity_level(model, BLDG.Room) == "space"
    assert validate_entity(model, BLDG.Point)["status"] == "green"
    assert "space" in catalog_for_level("space")
    assert "floor" not in catalog_for_level("space")
    assert {"space", "zone", "room"} <= set(guess_marker_bundle("Zone room", "space")["markers"])
