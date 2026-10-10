#!/usr/bin/env python3
"""Lesson 4 — run open-fdd FC1 locally on the lesson-3 DataFrame.

  Server = model + timeseries.  Laptop = fault math.

  uv run python scripts/lesson_04_run_fc1.py
"""

from __future__ import annotations

import warnings

from lesson_03_fc1_dataframe import build_fc1_dataframe  # noqa: E402
from lesson_helpers import banner, client  # noqa: E402
from open_fdd.rules import run_rule

# --- edit these (keep in sync across lesson_0*.py if you chain them) ---------
BASE_URL = "https://sparql-playground.onrender.com"
# BASE_URL = "http://127.0.0.1:8000"

EQUIPMENT = "AHU_1"

POLL_SECONDS = 300  # 5-minute samples in this dataset
# ----------------------------------------------------------------------------

warnings.filterwarnings("ignore", category=FutureWarning, module=r"open_fdd\.rules\.evidence")


def main() -> None:
    banner("Lesson 4 — run FC1 on this machine", base_url=BASE_URL, equipment=EQUIPMENT)

    with client(BASE_URL) as http:
        df = build_fc1_dataframe(http, quiet=True)

    print(f"\nLoaded {len(df)} rows × {len(df.columns)} roles — calling run_rule('FC1')…")
    res = run_rule("FC1", df, poll_seconds=POLL_SECONDS)

    print(f"\n  status              {res.status}")
    print(f"  fault_hours         {res.fault_hours}")
    print(f"  fault_pct           {res.fault_pct}")
    print(f"  sample_count        {res.sample_count}")
    print(f"  fault_sample_count  {res.fault_sample_count}")

    evidence = res.to_dict().get("evidence", {}) if hasattr(res, "to_dict") else {}
    intervals = (evidence.get("confirmed_fault") or {}).get("fault_intervals") or []
    if intervals:
        print("\nFirst fault intervals:")
        for iv in intervals[:5]:
            print(f"  {iv}")

    print("\nDone. Try another EQUIPMENT / date window, or add a .rq under scripts/sparql/")


if __name__ == "__main__":
    main()
