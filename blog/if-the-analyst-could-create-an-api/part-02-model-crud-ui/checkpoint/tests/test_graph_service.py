import contextlib
from pathlib import Path
from unittest.mock import patch

from bldgts.graph.service import GraphService
from bldgts.settings import Settings


def test_atomic_snapshot_survives_error(settings: Settings):
    g = GraphService(settings)
    settings.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with patch.object(g, "serialize_atomic", wraps=g.serialize_atomic):
        real_open = Path.open

        def flaky_open(self, *args, **kwargs):
            if str(self).endswith(".tmp") and kwargs.get("mode", "r") == "w":
                raise OSError("disk full")
            return real_open(self, *args, **kwargs)

        with patch.object(Path, "open", flaky_open), contextlib.suppress(OSError):
            g.serialize_atomic()
    assert not list(settings.snapshot_path.parent.glob("*.tmp"))


def test_shutdown_flush(settings: Settings):
    g = GraphService(settings)
    g._dirty = True
    g.serialize_atomic()
    assert settings.snapshot_path.exists()


def test_snapshot_does_not_mark_concurrent_mutation_clean(settings: Settings):
    from bldgts.graph.namespaces import BLDG
    from rdflib import Literal
    from rdflib.namespace import RDFS

    graph = GraphService(settings)
    real_write = graph._atomic_write_text
    changed = False

    def write_and_mutate(path, data):
        nonlocal changed
        if path == settings.tutorial_ttl_path and not changed:
            changed = True
            graph.apply_mutation(
                lambda model: model.set((BLDG.AHU_1, RDFS.label, Literal("During snapshot")))
            )
        real_write(path, data)

    with patch.object(graph, "_atomic_write_text", side_effect=write_and_mutate):
        graph.serialize_atomic()
    assert graph.dirty
    graph.serialize_atomic()
    assert not graph.dirty
    assert "During snapshot" in settings.snapshot_path.read_text()


def test_revision_write_failure_does_not_publish_mutation(settings: Settings):
    import pytest
    from bldgts.graph.namespaces import BLDG
    from rdflib import Literal
    from rdflib.namespace import RDFS

    graph = GraphService(settings)
    original_state = graph.state
    with (
        patch.object(graph, "_write_revision", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        graph.apply_mutation(
            lambda model: model.set((BLDG.AHU_1, RDFS.label, Literal("Unsaved")))
        )
    assert graph.state is original_state
    assert graph.revision == 0
    assert not graph.dirty
