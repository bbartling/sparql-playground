import contextlib
from pathlib import Path
from unittest.mock import patch

from brickts.graph.service import GraphService
from brickts.settings import Settings


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
