"""Portable Turtle and crash snapshots preserve authored RDF and opaque TS refs."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from bldgts.graph.service import GraphService
from bldgts.haystack.metadata import local_name, metadata
from bldgts.services.model_crud import apply_metadata, rename_entity
from rdflib import Graph, Literal
from rdflib.compare import isomorphic
from rdflib.namespace import RDFS
from rdflib.plugins.parsers.notation3 import BadSyntax

POINT_QUERY = """
PREFIX bts: <https://example.org/openfdd/bldgts#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
SELECT ?point ?owner ?timeseries WHERE {
  ?point bts:hasHaystackMarker "point" ;
         bts:hasHaystackTag ?eref ;
         ref:hasExternalReference ?reference .
  ?eref bts:tagName "equipRef" ; bts:tagValue ?owner .
  ?reference ref:hasTimeseriesId ?timeseries .
} ORDER BY ?point LIMIT 1
"""
REFERENCE_QUERY = """
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
SELECT ?point ?timeseries ?database WHERE {
  ?point ref:hasExternalReference ?reference .
  ?reference ref:hasTimeseriesId ?timeseries ; ref:storedAt ?database .
}
"""


def discover_point(graph):
    # Model discovery uses SPARQL, never matching names or serialized RDF text.
    return next(iter(graph.state.model.query(POINT_QUERY)))


def references(graph):
    return {tuple(row) for row in graph.query(REFERENCE_QUERY)}


def author_metadata(graph, point, owner):
    values = {
        "dis": {"kind": "Str", "value": "Discharge pressure – renamed"},
        "kind": {"kind": "Str", "value": "Number"},
        "equipRef": {"kind": "Ref", "value": local_name(owner)},
        "curVal": {"kind": "Bool", "value": False},
        "minVal": {"kind": "Number", "value": 0},
        "maxVal": {"kind": "Number", "value": 12.5},
        "unit": {"kind": "Str", "value": "Pa"},
    }
    with patch.object(graph, "schedule_serialize"):
        result = apply_metadata(
            graph,
            updates=[
                {
                    "entity_id": local_name(point),
                    "markers": ["point", "sensor"],
                    "metadata": values,
                }
            ],
            expected_revision=graph.revision,
            allow_mutations=True,
        )
    assert result["ok"], result
    return values


def test_serialized_metadata_and_references_survive_a_fresh_service(settings):
    settings.allow_mutations = True
    graph = GraphService(settings)
    point, owner, _ = discover_point(graph)
    original_refs = references(graph.state.model)
    values = author_metadata(graph, point, owner)
    revision = graph.revision
    graph.serialize_atomic()
    assert not graph.dirty

    # Both user-facing and recovery exports contain the complete model, not ontology.
    for path in (settings.tutorial_ttl_path, settings.snapshot_path):
        saved = Graph().parse(path, format="turtle")
        assert isomorphic(saved, graph.state.model)
        assert metadata(saved, point) == values
        assert references(saved) == original_refs

    restored = GraphService(settings)
    assert restored.revision == revision
    assert not restored.dirty
    assert isomorphic(restored.state.model, graph.state.model)
    assert metadata(restored.state.model, point) == values
    assert references(restored.state.model) == original_refs

    with patch.object(restored, "schedule_serialize"):
        result = rename_entity(
            restored,
            entity_id=local_name(point),
            label="After reboot",
            expected_revision=revision,
            allow_mutations=True,
        )
    assert result["ok"] and result["revision"] == revision + 1
    restored.serialize_atomic()
    rebooted = GraphService(settings)
    assert rebooted.revision == revision + 1
    assert metadata(rebooted.state.model, point)["dis"]["value"] == "After reboot"
    assert references(rebooted.state.model) == original_refs


def test_transferred_turtle_is_a_complete_portable_seed(settings, tmp_path):
    settings.allow_mutations = True
    graph = GraphService(settings)
    point, owner, _ = discover_point(graph)
    values = author_metadata(graph, point, owner)
    graph.serialize_atomic()
    # BLDGTS_MODEL_PATH already supports loading a Turtle export on another host.
    destination = settings.model_copy(
        update={
            "model_path": settings.tutorial_ttl_path,
            "snapshot_path": tmp_path / "other-host" / "snapshot.ttl",
            "tutorial_ttl_path": tmp_path / "other-host" / "building.ttl",
        }
    )
    restored = GraphService(destination)
    assert isomorphic(restored.state.model, graph.state.model)
    assert metadata(restored.state.model, point) == values
    assert references(restored.state.model) == references(graph.state.model)
    assert restored.revision == 0  # Revisions belong to the local recovery journal.


def test_snapshot_wins_only_when_at_least_as_new_as_seed(settings):
    graph = GraphService(settings)
    point, _, _ = discover_point(graph)
    graph.apply_mutation(lambda model: model.set((point, RDFS.label, Literal("Saved edit"))))
    graph.serialize_atomic()
    os.utime(settings.model_path, (100, 100))
    os.utime(settings.snapshot_path, (200, 200))
    snapshot = GraphService(settings)
    assert snapshot.revision == 1
    assert str(snapshot.state.model.value(point, RDFS.label)) == "Saved edit"

    os.utime(settings.model_path, (300, 300))
    seed = GraphService(settings)
    assert seed.revision == 0
    assert isomorphic(seed.state.model, Graph().parse(settings.model_path, format="turtle"))
    assert str(seed.state.model.value(point, RDFS.label)) != "Saved edit"


def test_crash_before_next_flush_recovers_the_previous_snapshot_revision(settings):
    graph = GraphService(settings)
    point, _, _ = discover_point(graph)
    graph.apply_mutation(lambda model: model.set((point, RDFS.label, Literal("Persisted"))))
    graph.serialize_atomic()
    graph.apply_mutation(lambda model: model.set((point, RDFS.label, Literal("Unflushed"))))
    assert graph.revision == 2
    ledger = json.loads(graph._revision_path().read_text())
    assert ledger["revision"] == 2
    assert ledger["snapshot_revision"] == 1
    # A new process sees a truthful last completed snapshot and its matching revision.
    rebooted = GraphService(settings)
    assert rebooted.revision == 1
    assert str(rebooted.state.model.value(point, RDFS.label)) == "Persisted"


def test_concurrent_mutation_keeps_snapshot_revision_tied_to_its_bytes(settings):
    graph = GraphService(settings)
    point, _, _ = discover_point(graph)
    graph.apply_mutation(lambda model: model.set((point, RDFS.label, Literal("Revision one"))))
    real_write = graph._atomic_write_text
    changed = False

    def mutate_during_write(path, data):
        nonlocal changed
        if path == settings.tutorial_ttl_path and not changed:
            changed = True
            graph.apply_mutation(
                lambda model: model.set((point, RDFS.label, Literal("Revision two")))
            )
        real_write(path, data)

    with patch.object(graph, "_atomic_write_text", side_effect=mutate_during_write):
        graph.serialize_atomic()
    assert graph.dirty and graph.revision == 2
    rebooted = GraphService(settings)
    assert rebooted.revision == 1
    assert str(rebooted.state.model.value(point, RDFS.label)) == "Revision one"
    graph.serialize_atomic()
    assert not graph.dirty
    rebooted = GraphService(settings)
    assert rebooted.revision == 2
    assert str(rebooted.state.model.value(point, RDFS.label)) == "Revision two"


def test_atomic_write_failure_preserves_old_snapshot_and_removes_temporary_file(settings):
    graph = GraphService(settings)
    graph.serialize_atomic()
    original = settings.snapshot_path.read_bytes()
    real_replace = os.replace

    def fail_snapshot(source, destination):
        if Path(destination) == settings.snapshot_path:
            raise OSError("disk full")
        return real_replace(source, destination)

    point, _, _ = discover_point(graph)
    graph.apply_mutation(lambda model: model.set((point, RDFS.label, Literal("Unsaved"))))
    with (
        patch("bldgts.graph.service.os.replace", side_effect=fail_snapshot),
        pytest.raises(OSError, match="disk full"),
    ):
        graph.serialize_atomic()
    assert graph.dirty
    assert settings.snapshot_path.read_bytes() == original
    assert not list(settings.snapshot_path.parent.glob("*.tmp"))
    assert GraphService(settings).revision == 0


@pytest.mark.parametrize("journal", ["not json", "[]", '{"revision": 999999}'])
def test_missing_or_malformed_recovery_metadata_preserves_rdf_with_fresh_revision(
    settings, journal
):
    graph = GraphService(settings)
    graph.serialize_atomic()
    graph._revision_path().write_text(journal)
    rebooted = GraphService(settings)
    assert rebooted.revision == 0
    assert isomorphic(rebooted.state.model, graph.state.model)


def test_changed_snapshot_cannot_reuse_an_unrelated_revision(settings):
    graph = GraphService(settings)
    point, _, _ = discover_point(graph)
    graph.apply_mutation(lambda model: model.set((point, RDFS.label, Literal("Before"))))
    graph.serialize_atomic()
    changed = Graph().parse(settings.snapshot_path, format="turtle")
    changed.set((point, RDFS.label, Literal("Manual edit")))
    changed.serialize(settings.snapshot_path, format="turtle")
    restored = GraphService(settings)
    assert restored.revision == 0
    assert str(restored.state.model.value(point, RDFS.label)) == "Manual edit"


def test_corrupt_newer_snapshot_fails_instead_of_silently_losing_edits(settings):
    graph = GraphService(settings)
    graph.serialize_atomic()
    settings.snapshot_path.write_text("this is not valid Turtle {")
    with pytest.raises(BadSyntax):
        GraphService(settings)
    assert settings.snapshot_path.read_text() == "this is not valid Turtle {"


def test_startup_parser_is_turtle_only_even_for_a_misleading_file_extension(settings, tmp_path):
    turtle = tmp_path / "transferred.jsonld"
    source = Graph().parse(settings.model_path, format="turtle")
    source.serialize(turtle, format="turtle")
    loaded = GraphService(settings.model_copy(update={"model_path": turtle}))
    assert isomorphic(loaded.state.model, source)
    turtle.write_text('{"@context":"https://invalid.example/context.jsonld","@id":"urn:test"}')
    with pytest.raises(BadSyntax):
        GraphService(settings.model_copy(update={"model_path": turtle}))
