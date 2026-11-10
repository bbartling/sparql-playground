# Day 16 (pandas): count FC1 raw faults and fan run hours with a Python loop and with pandas.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day16_pandas.py

import time

import pandas as pd

TOLERANCE_PA = 25  # how far below setpoint counts as "too low"
HOURS_PER_ROW = 5 / 60  # one row = 5 minutes

results = []
for n in [10_000, 100_000, 1_000_000]:
    # 1. Read the first n rows of the synthetic data
    start = time.perf_counter()
    df = pd.read_csv("var/synthetic_ahu.csv", nrows=n)
    read_seconds = time.perf_counter() - start

    # 2. Version (a): a plain Python loop, one row at a time
    fan = df["fan_status"].tolist()
    static = df["static_pa"].tolist()
    setpoint = df["setpoint_pa"].tolist()

    start = time.perf_counter()
    fault_rows = 0
    run_rows = 0
    for i in range(n):
        if fan[i] == 1:
            run_rows = run_rows + 1
            if static[i] < setpoint[i] - TOLERANCE_PA:
                fault_rows = fault_rows + 1
    loop_seconds = time.perf_counter() - start

    # 3. Version (b): pandas, whole columns at once
    start = time.perf_counter()
    fan_on = df["fan_status"] == 1
    too_low = df["static_pa"] < df["setpoint_pa"] - TOLERANCE_PA
    pandas_fault_rows = (fan_on & too_low).sum()
    pandas_run_rows = fan_on.sum()
    pandas_seconds = time.perf_counter() - start

    print("rows:", n)
    print("  fault rows:", pandas_fault_rows)
    print("  run hours: ", round(pandas_run_rows * HOURS_PER_ROW, 1))
    print("  loop gives the same answer:", fault_rows == pandas_fault_rows)
    print(
        "  seconds: read CSV",
        round(read_seconds, 3),
        "| loop",
        round(loop_seconds, 3),
        "| pandas",
        round(pandas_seconds, 4),
    )

    results.append(
        {
            "rows": n,
            "fault_rows": int(pandas_fault_rows),
            "run_hours": pandas_run_rows * HOURS_PER_ROW,
        }
    )

fault_by_size = pd.DataFrame(results)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fault_by_size": fault_by_size}
