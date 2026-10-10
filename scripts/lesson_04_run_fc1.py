#!/usr/bin/env python3
"""Lesson 4 — run open-fdd FC1 locally on the lesson-3 DataFrame.

  Server = model + timeseries.  Laptop = fault math.

  uv run python scripts/lesson_04_run_fc1.py
"""

from __future__ import annotations

import warnings

from lesson_03_fc1_dataframe import build_fc1_dataframe  # noqa: E402
from lesson_config import POLL_SECONDS, banner, client  # noqa: E402
from open_fdd.rules import run_rule

warnings.filterwarnings("ignore", category=FutureWarning, module=r"open_fdd\.rules\.evidence")


def main() -> None:
    banner("Lesson 4 — run FC1 on this machine")

    with client() as http:
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

    print("\nDone. More rules →  scripts/analyst_client.py")


if __name__ == "__main__":
    main()
