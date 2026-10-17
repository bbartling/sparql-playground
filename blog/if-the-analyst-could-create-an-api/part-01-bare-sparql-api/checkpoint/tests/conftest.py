from __future__ import annotations

from pathlib import Path

import pytest

from brickts.graph.render import render_model, write_turtle
from brickts.settings import Settings


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def sample_csv(project_root: Path, tmp_path_factory) -> Path:
    src = project_root / "data/BUILDING_50/AHU_1/history_wide.csv"
    dst_dir = tmp_path_factory.mktemp("csv")
    dst = dst_dir / "history_wide.csv"
    with src.open() as fin, dst.open("w") as fout:
        for i, line in enumerate(fin):
            if i > 2000:
                break
            fout.write(line)
    return dst


@pytest.fixture
def settings(project_root: Path, tmp_path: Path, sample_csv: Path) -> Settings:
    var = tmp_path / "var"
    var.mkdir()
    db = var / "ts.sqlite"
    snap = var / "snap.ttl"
    model = tmp_path / "model.ttl"
    site = project_root / "model/site.ttl"
    mapping = project_root / "model/points/BUILDING_50__AHU_1.csv"
    render_model(site, mapping)
    write_turtle(render_model(site, mapping), model)
    datasets = tmp_path / "datasets.json"
    datasets.write_text(
        f'[{{"building":"BUILDING_50","equipment":"AHU_1","csv":"{sample_csv}","mapping":"{mapping}"}}]'
    )
    return Settings(
        data_dir=project_root / "data",
        db_path=db,
        model_path=model,
        site_model_path=site,
        points_dir=project_root / "model/points",
        datasets_path=datasets,
        snapshot_path=snap,
        bootstrap_on_startup=False,
        serialize_interval_s=0,
    )
