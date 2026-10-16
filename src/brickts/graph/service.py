from __future__ import annotations

import logging
import os
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph

from brickts.graph.ontology import load_brick_ontology
from brickts.graph.render import render_model, write_turtle
from brickts.graph.validate import run_sparql_checks
from brickts.settings import Settings

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
            return int(data.get("revision") or 0)
        except (OSError, ValueError, TypeError):
            return 0

    def _write_revision(self, revision: int, *, note: str = "") -> None:
        import json
        from datetime import UTC, datetime

        path = self._revision_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "revision": revision,
                    "updated_at": datetime.now(UTC)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "note": note,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _load_initial(self) -> GraphState:
        seed = self._settings.model_path
        snap = self._settings.snapshot_path
        load_path = seed
        if snap.exists() and (not seed.exists() or snap.stat().st_mtime >= seed.stat().st_mtime):
            load_path = snap
        model = Graph()
        if load_path.exists():
            model.parse(load_path, format="turtle")
        return GraphState(model=model, union=model + self._ontology)

    def _rebuild_union(self, model: Graph) -> GraphState:
        return GraphState(model=model, union=model + self._ontology)

    def reload_from_disk(self) -> None:
        with self._lock:
            self._state = self._load_initial()
            self._dirty = False
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
            self._state = self._rebuild_union(new_model)
            self._dirty = True
            self._revision += 1
            self._write_revision(self._revision, note=note)
            return self._revision

    def _atomic_write_text(self, path: Path, data: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def serialize_atomic(self) -> None:
        """Write Turtle to repo-root ``building.ttl`` (tutorial) and ``var/`` snapshot."""
        with self._serialize_lock:
            data = self._state.model.serialize(format="turtle")
            tutorial = self._settings.tutorial_ttl_path
            snapshot = self._settings.snapshot_path
            self._atomic_write_text(tutorial, data)
            if snapshot.resolve() != tutorial.resolve():
                self._atomic_write_text(snapshot, data)
            self._dirty = False
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

        threading.Thread(target=_run, name="brickts-serialize", daemon=True).start()

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
