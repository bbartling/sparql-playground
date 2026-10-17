import csv
from pathlib import Path

import pytest
from bldgts.graph.namespaces import BLDG, BTS, REF
from bldgts.haystack.metadata import markers_of
from bldgts.settings import Settings
from bldgts.store.sqlite import SqliteTimeseriesStore
from rdflib import Graph, Literal


@pytest.fixture
def model(project_root: Path) -> Graph:
    g = Graph()
    g.parse(project_root / "model/building_50.ttl", format="turtle")
    return g


def test_model_counts(model: Graph):
    sites = [
        s
        for s in model.subjects(BTS.hasHaystackMarker, Literal("site"))
        if str(s).startswith(str(BLDG))
    ]
    assert len(sites) == 1
    ahuis = [
        s
        for s in model.subjects(BTS.hasHaystackMarker, Literal("ahu"))
        if str(s).startswith(str(BLDG))
    ]
    assert len(ahuis) == 2
    points = list(model.subjects(REF.hasExternalReference, None))
    assert len(points) == 118
    assert all("point" in markers_of(model, p) for p in points if str(p).startswith(str(BLDG)))


def test_refs_and_store(project_root: Path, settings: Settings):
    import asyncio

    bootstrap_from = __import__("bldgts.ingest", fromlist=["bootstrap_all"]).bootstrap_all
    s = settings
    bootstrap_from(s)
    union = Graph()
    union.parse(s.model_path, format="turtle")

    async def check() -> None:
        store = SqliteTimeseriesStore(s.db_path)
        ids: set[str] = set()
        for p in union.subjects(REF.hasExternalReference, None):
            for ref in union.objects(p, REF.hasExternalReference):
                for tid in union.objects(ref, REF.hasTimeseriesId):
                    ids.add(str(tid))
                    assert await store.exists(str(tid))
        # Settings fixture renders AHU_1 only (see tests/conftest.py).
        assert len(ids) == 83
        await store.close()

    asyncio.run(check())


def test_mapping_csv_frozen(project_root: Path):
    rows = []
    for path in sorted((project_root / "model/points").glob("*.csv")):
        with path.open() as f:
            rows.extend(csv.DictReader(f))
    assert len(rows) == 118
    assert all(r["timeseries_id"] for r in rows)


def test_mapping_no_csv_literals(project_root: Path, model: Graph):
    del model
    mapping = project_root / "model/points/BUILDING_50__AHU_1.csv"
    ttl = (project_root / "model/building_50.ttl").read_text()
    with mapping.open() as f:
        for row in csv.DictReader(f):
            assert row["source_column"] not in ttl


def test_shacl(project_root: Path):
    # SHACL over Brick ontology is retired with the Haystack-only cutover.
    pytest.skip("Brick SHACL not used for the Haystack application model")
