import asyncio
import csv
from pathlib import Path

from brickts.ingest import bootstrap_all, bootstrap_dataset
from brickts.settings import Settings
from brickts.store.sqlite import SqliteTimeseriesStore


async def _bootstrap_idempotent(settings: Settings, sample_csv: Path, mapping: Path) -> None:
    store = SqliteTimeseriesStore(settings.db_path)
    r1 = await bootstrap_dataset(
        store,
        dataset_key="BUILDING_50/AHU_1",
        csv_path=sample_csv,
        mapping_path=mapping,
    )
    assert r1 == "loaded"
    r2 = await bootstrap_dataset(
        store,
        dataset_key="BUILDING_50/AHU_1",
        csv_path=sample_csv,
        mapping_path=mapping,
    )
    assert r2 == "skipped"
    r3 = await bootstrap_dataset(
        store,
        dataset_key="BUILDING_50/AHU_1",
        csv_path=sample_csv,
        mapping_path=mapping,
        force=True,
    )
    assert r3 == "loaded"
    await store.close()


def test_bootstrap_idempotent(settings: Settings, sample_csv: Path, project_root: Path):
    mapping = project_root / "model/points/BUILDING_50__AHU_1.csv"
    asyncio.run(_bootstrap_idempotent(settings, sample_csv, mapping))


def test_all_columns_mapped(settings: Settings, sample_csv: Path, project_root: Path):
    mapping = project_root / "model/points/BUILDING_50__AHU_1.csv"
    with mapping.open() as f:
        mapped = {r["source_column"] for r in csv.DictReader(f)}
    import pandas as pd

    cols = [c for c in pd.read_csv(sample_csv, nrows=0).columns if c != "timestamp_utc"]
    assert len(mapped) == 83
    assert set(cols) == mapped
    bootstrap_all(settings)

    async def check_ids() -> None:
        store = SqliteTimeseriesStore(settings.db_path)
        assert len(await store.series_ids()) >= 1
        await store.close()

    asyncio.run(check_ids())
