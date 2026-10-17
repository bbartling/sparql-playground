from __future__ import annotations

from pathlib import Path

from rdflib import Graph, URIRef

from brickts.graph.namespaces import BRICK, BTS, RDF, REF
from brickts.settings import Settings
from brickts.store.base import TimeseriesStore
from brickts.store.sqlite import SqliteTimeseriesStore

BACKENDS: dict[str, type[SqliteTimeseriesStore]] = {
    "sqlite": SqliteTimeseriesStore,
}


def build_store_registry(
    union: Graph,
    settings: Settings,
    *,
    db_path: Path | None = None,
) -> dict[str, TimeseriesStore]:
    stores: dict[str, TimeseriesStore] = {}
    db_path = db_path or settings.db_path
    db_nodes = set(union.subjects(RDF.type, REF.Database)) | set(
        union.subjects(RDF.type, BRICK.Database)
    )
    for db_node in db_nodes:
        if not isinstance(db_node, URIRef):
            continue
        backend_vals = list(union.objects(db_node, BTS.backend))
        if not backend_vals:
            continue
        backend = str(backend_vals[0])
        impl = BACKENDS.get(backend)
        if impl is None:
            continue
        path = db_path
        stores[str(db_node)] = impl(path)
    if not stores:
        # Fallback: single sqlite store for tutorial
        stores["https://example.org/openfdd/BUILDING_50#timeseries_db"] = SqliteTimeseriesStore(
            db_path
        )
    return stores


def database_iri_for_backend(
    stores: dict[str, TimeseriesStore], backend: str = "sqlite"
) -> str | None:
    for iri, store in stores.items():
        if backend == "sqlite" and isinstance(store, SqliteTimeseriesStore):
            return iri
    return next(iter(stores.keys()), None)
