import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from brickts.api.app import create_app
from brickts.ingest import bootstrap_all
from brickts.settings import Settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyst_client import find_one, run_fc1  # noqa: E402


def test_client_fc1(settings: Settings):
    bootstrap_all(settings)
    app = create_app(settings)

    class _Adapter:
        def __init__(self, tc: TestClient) -> None:
            self._tc = tc

        def get(self, path: str, **kwargs):
            return self._tc.get(path, **kwargs)

    with TestClient(app) as tc:
        client = _Adapter(tc)
        dsp = find_one(client, "AHU_1", brick_class="Supply_Air_Static_Pressure_Sensor")
        sp = find_one(client, "AHU_1", tags="Supply,Air,Static,Pressure,Setpoint")
        fan = find_one(client, "AHU_1", brick_class="Fan_Speed_Command", parent_class="Supply_Fan")
        assert dsp and sp and fan
        run_fc1(client, "AHU_1")


def test_fc1_raw_mask_semantics():
    # synthetic window: fan high, dsp below sp - 0.12
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
