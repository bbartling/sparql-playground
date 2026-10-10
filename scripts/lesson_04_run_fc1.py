#!/usr/bin/env python3
"""Lesson 4 — run Open-FDD FC1 locally on the DataFrame from lesson 3.

Server only supplied the model + timeseries. The fault math runs here.

  uv run python scripts/lesson_04_run_fc1.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

from open_fdd.rules import run_rule

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lesson_01_mech_summary import client  # noqa: E402
from lesson_03_fc1_dataframe import build_fc1_dataframe  # noqa: E402
from lesson_config import BASE_URL, EQUIPMENT, POLL_SECONDS  # noqa: E402

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"open_fdd\.rules\.evidence",
)


def main() -> None:
    print(f"BASE_URL = {BASE_URL}")
    print(f"EQUIPMENT = {EQUIPMENT}")
    print("Crunching FC1 on this machine (not on the server)…")

    with client() as http:
        df = build_fc1_dataframe(http)

    res = run_rule("FC1", df, poll_seconds=POLL_SECONDS)
    print("\nFC1 result:")
    print(f"  status            = {res.status}")
    print(f"  fault_hours       = {res.fault_hours}")
    print(f"  fault_pct         = {res.fault_pct}")
    print(f"  sample_count      = {res.sample_count}")
    print(f"  fault_sample_count= {res.fault_sample_count}")

    evidence = res.to_dict().get("evidence", {}) if hasattr(res, "to_dict") else {}
    intervals = (evidence.get("confirmed_fault") or {}).get("fault_intervals") or []
    if intervals:
        print("\nFirst fault intervals:")
        for iv in intervals[:5]:
            print(" ", iv)

    print("\nDone. For more rules / all AHUs, use scripts/analyst_client.py")


if __name__ == "__main__":
    main()
