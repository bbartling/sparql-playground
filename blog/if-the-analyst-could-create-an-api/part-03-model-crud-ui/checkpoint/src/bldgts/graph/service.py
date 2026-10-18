from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from bldgts.graph.ontology import load_brick_ontology
from bldgts.graph.render import render_model, write_turtle
from bldgts.graph.validate import run_sparql_checks
from bldgts.settings import Settings
from rdflib import Graph

log = logging.getLogger(__name__)


@dataclass
class GraphState:
    model: Graph
    union: Graph


class GraphService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._serialize_lock = threading.Lock()
        self._ontology = load_brick_ontology()
        self._dirty = False
        self._revision = 0
        self._snapshot_revision = 0
        self._snapshot_sha256: str | None = None
        self._loaded_snapshot_sha256: str | None = None
        self._state = self._load_initial()
        self._revision = self._load_revision()

    @property
    def state(self) -> GraphState:
        return self._state

    @property
    def ontology(self) -> Graph:
        return self._ontology

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def revision(self) -> int:
        return self._revision

    def mark_clean(self) -> None:
        self._dirty = False

    def _revision_path(self) -> Path:
        return self._settings.snapshot_path.with_suffix(".meta.json")

    def _load_revision(self) -> int:
        path = self._revision_path()
        if not path.is_file():
            return 0
        try:
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return 0
            # The mutation ledger may be newer than the last completed snapshot.
            # Only recover a revision proved to belong to the exact loaded bytes.
            digest = data.get("snapshot_sha256")
            if not self._loaded_snapshot_sha256 or digest != self._loaded_snapshot_sha256:
                return 0
            revision = int(data.get("snapshot_revision") or 0)
            if revision < 0:
                return 0
            self._snapshot_revision = revision
            self._snapshot_sha256 = digest
            return revision
        except (OSError, ValueError, TypeError):
            return 0

    def _write_revision(
        self,
        revision: int,
        *,
        note: str = "",
        snapshot_revision: int | None = None,
        snapshot_sha256: str | None = None,
    ) -> None:
        import json
        from datetime import UTC, datetime

        path = self._revision_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_text(
            path,
            json.dumps(
                {
                    "revision": revision,
                    "snapshot_revision": (
                        self._snapshot_revision if snapshot_revision is None else snapshot_revision
                    ),
                    "snapshot_sha256": snapshot_sha256 or self._snapshot_sha256,
                    "updated_at": datetime.now(UTC)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "note": note,
                },
                indent=2,
            )
            + "\n",
        )

    def _load_initial(self) -> GraphState:
        seed = self._settings.model_path
        snap = self._settings.snapshot_path
        load_path = seed
        if snap.exists() and (not seed.exists() or snap.stat().st_mtime >= seed.stat().st_mtime):
            load_path = snap
        model = Graph()
        self._loaded_snapshot_sha256 = None
        if load_path.exists():
            data = load_path.read_bytes()
            # Always use Turtle, including transferred files with unfamiliar suffixes.
            # Parsing RDF/XML or JSON-LD here could introduce external fetch behavior.
            model.parse(data=data, format="turtle", publicID=load_path.resolve().as_uri())
            if load_path.resolve() == snap.resolve():
                self._loaded_snapshot_sha256 = hashlib.sha256(data).hexdigest()
        return GraphState(model=model, union=model + self._ontology)

    def _rebuild_union(self, model: Graph) -> GraphState:
        return GraphState(model=model, union=model + self._ontology)

    def reload_from_disk(self) -> None:
        with self._serialize_lock, self._lock:
            self._state = self._load_initial()
            self._dirty = False
            self._snapshot_revision = 0
            self._snapshot_sha256 = None
            self._revision = self._load_revision()

    def add_triples(self, triples: list[tuple]) -> None:
        def mutator(g: Graph) -> None:
            for t in triples:
                g.add(t)

        self.apply_mutation(mutator, note="add_triples")

    def apply_mutation(
        self,
        mutator: Callable[[Graph], None],
        *,
        note: str = "",
        expected_revision: int | None = None,
    ) -> int:
        """Copy-on-write mutate the model graph. Returns the new revision."""
        with self._lock:
            if expected_revision is not None and expected_revision != self._revision:
                raise ConflictError(
                    current=self._revision,
                    expected=expected_revision,
                )
            new_model = Graph()
            for t in self._state.model:
                new_model.add(t)
            mutator(new_model)
            issues = run_sparql_checks(new_model, self._ontology)
            for issue in issues:
                if issue.check == "missing_refs" and issue.count > 0:
                    raise ValueError("ref validation failed after mutation")
            new_state = self._rebuild_union(new_model)
            new_revision = self._revision + 1
            self._write_revision(new_revision, note=note)
            self._state = new_state
            self._dirty = True
            self._revision = new_revision
            return new_revision

    def _atomic_write_text(self, path: Path, data: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            # Commit the directory entry as well as file contents on POSIX hosts.
            if hasattr(os, "O_DIRECTORY"):
                directory = os.open(path.parent, os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def serialize_atomic(self) -> None:
        """Write Turtle to repo-root ``building.ttl`` (tutorial) and ``var/`` snapshot."""
        with self._serialize_lock:
            with self._lock:
                state = self._state
                revision = self._revision
            data = state.model.serialize(format="turtle")
            tutorial = self._settings.tutorial_ttl_path
            snapshot = self._settings.snapshot_path
            self._atomic_write_text(tutorial, data)
            if snapshot.resolve() != tutorial.resolve():
                self._atomic_write_text(snapshot, data)
            digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
            with self._lock:
                # A mutation during this write still needs its own snapshot; its
                # ledger revision must not be attributed to these older RDF bytes.
                self._write_revision(
                    self._revision,
                    note="snapshot",
                    snapshot_revision=revision,
                    snapshot_sha256=digest,
                )
                self._snapshot_revision = revision
                self._snapshot_sha256 = digest
                self._dirty = self._revision != revision
            log.info(
                "graph turtle written",
                extra={"tutorial": str(tutorial), "snapshot": str(snapshot)},
            )

    def schedule_serialize(self) -> None:
        """Serialize Turtle on a daemon thread (safe to call from request handlers)."""

        def _run() -> None:
            try:
                self.serialize_atomic()
            except Exception:  # noqa: BLE001 - background flush must not crash the app
                log.exception("background graph serialize failed")

        threading.Thread(target=_run, name="bldgts-serialize", daemon=True).start()

    def build_seed_model(self, site_path: Path, points_csv: Path, out_path: Path) -> None:
        model = render_model(site_path, points_csv)
        write_turtle(model, out_path)


class ConflictError(Exception):
    def __init__(self, *, current: int, expected: int) -> None:
        self.current = current
        self.expected = expected
        super().__init__(f"revision mismatch: current={current} expected={expected}")


def build_union_model(model: Graph, ontology: Graph | None = None) -> Graph:
    ont = ontology or load_brick_ontology()
    return model + ont
