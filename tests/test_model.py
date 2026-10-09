import csv
from pathlib import Path

import pytest
from rdflib import Graph

from brickts.graph.namespaces import BLDG, BRICK, RDF, REF
from brickts.graph.ontology import load_brick_ontology
from brickts.graph.validate import run_shacl
from brickts.settings import Settings
from brickts.store.sqlite import SqliteTimeseriesStore


@pytest.fixture
def union(project_root: Path) -> Graph:
    g = Graph()
    g.parse(project_root / "model/building_50.ttl", format="turtle")
    return g + load_brick_ontology()


def test_model_counts(union: Graph):
    sites = list(union.subjects(RDF.type, BRICK.Site))
    assert len(sites) == 1
    ahuis = [
        s for s in union.subjects(RDF.type, BRICK.Air_Handler_Unit) if str(s).startswith(str(BLDG))
    ]
    assert len(ahuis) == 1
    points = [
        s
        for s in union.subjects(RDF.type, None)
        if str(s).startswith(str(BLDG)) and (s, BRICK.isPointOf, None) in union
    ]
    assert len(points) == 83


def test_refs_and_store(project_root: Path, union: Graph, settings: Settings):
    import asyncio

    bootstrap_from = __import__("brickts.ingest", fromlist=["bootstrap_all"]).bootstrap_all
    s = settings
    bootstrap_from(s)

    async def check() -> None:
        store = SqliteTimeseriesStore(s.db_path)
        ids: set[str] = set()
        for p in union.subjects(BRICK.isPointOf, None):
            if not str(p).startswith(str(BLDG)):
                continue
            refs = list(union.objects(p, REF.hasExternalReference))
            assert len(refs) == 1
            ts_ids = list(union.objects(refs[0], REF.hasTimeseriesId))
            assert len(ts_ids) == 1
            db = list(union.objects(refs[0], REF.storedAt))
            assert len(db) == 1
            tid = str(ts_ids[0])
            assert tid not in ids
            ids.add(tid)
            assert await store.exists(tid)
        await store.close()

    asyncio.run(check())


def test_mapping_no_csv_literals(project_root: Path, union: Graph):
    mapping = project_root / "model/points/BUILDING_50__AHU_1.csv"
    ttl = (project_root / "model/building_50.ttl").read_text()
    with mapping.open() as f:
        for row in csv.DictReader(f):
            assert row["source_column"] not in ttl


def test_shacl(project_root: Path):
    model = Graph()
    model.parse(project_root / "model/building_50.ttl", format="turtle")
    ok, _ = run_shacl(model, load_brick_ontology())
    if _ != "pyshacl not installed; skipped":
        assert ok
