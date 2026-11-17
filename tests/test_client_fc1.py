"""FC1 path used by the lesson scripts (SPARQL → timeseries → run_rule)."""

import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lesson_02_fc1_points import find_fc1_points  # noqa: E402


class _HttpxLike:
    def __init__(self, tc: TestClient):
        self._tc = tc

    def post(self, path, **kwargs):
        return self._tc.post(path, **kwargs)

    def get(self, path, **kwargs):
        return self._tc.get(path, **kwargs)


def test_lesson_fc1_sparql_and_series(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)
    with TestClient(app) as tc:
        http = _HttpxLike(tc)
        points = find_fc1_points(http, quiet=True)
        assert set(points) == {
            "duct-static-pressure",
            "duct-static-pressure-sp",
            "fan-cmd",
        }
        series = {}
        for role, pid in points.items():
            r = http.get(f"/api/points/{pid}/timeseries", params={"limit": 200})
            assert r.status_code == 200
            samples = r.json()["samples"]
            assert len(samples) >= 50
            idx = pd.to_datetime([s["ts"] for s in samples], unit="s", utc=True)
            series[role] = pd.Series([s["value"] for s in samples], index=idx)
        df = pd.DataFrame(series).sort_index()
        assert len(df) >= 50


def test_fc1_raw_mask_semantics():
    idx = pd.date_range("2026-01-01", periods=5, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "duct-static-pressure": [0.5, 0.5, 0.5, 0.5, 0.5],
            "duct-static-pressure-sp": [1.0, 1.0, 1.0, 1.0, 1.0],
            "fan-cmd": [90, 90, 90, 10, 90],
        },
        index=idx,
    )
    df.attrs.update(equipment_id="X", equipment_type="ahu")
    from open_fdd.rules import run_rule

    res = run_rule("FC1", df, poll_seconds=300)
    assert res.fault_sample_count >= 1
