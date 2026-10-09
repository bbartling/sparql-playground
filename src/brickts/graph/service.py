from __future__ import annotations

import logging
import os
import tempfile
import threading
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
        self._ontology = load_brick_ontology()
        self._dirty = False
        self._state = self._load_initial()

    @property
    def state(self) -> GraphState:
        return self._state

    @property
    def ontology(self) -> Graph:
        return self._ontology

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

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

    def add_triples(self, triples: list[tuple]) -> None:
        with self._lock:
            new_model = Graph()
            for t in self._state.model:
                new_model.add(t)
            for t in triples:
                new_model.add(t)
            issues = run_sparql_checks(new_model, self._ontology)
            for issue in issues:
                if issue.check == "missing_refs" and issue.count > 0:
                    raise ValueError("ref validation failed after mutation")
            self._state = self._rebuild_union(new_model)
            self._dirty = True

    def serialize_atomic(self) -> None:
        path = self._settings.snapshot_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self._state.model.serialize(format="turtle")
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            self._dirty = False
            log.info("graph snapshot written", extra={"path": str(path)})
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def build_seed_model(self, site_path: Path, points_csv: Path, out_path: Path) -> None:
        model = render_model(site_path, points_csv)
        write_turtle(model, out_path)


def build_union_model(model: Graph, ontology: Graph | None = None) -> Graph:
    ont = ontology or load_brick_ontology()
    return model + ont
