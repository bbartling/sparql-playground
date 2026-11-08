"""Day 16, pandas side: one answer two ways, a plain Python loop and vectorized pandas.

    uv run python lessons/unit2-python/day16_pandas.py

The question: on synthetic history (the same rows day16_sql.py loads into SQLite), how many
5-minute rows have the fan running with duct static more than 25 Pa below setpoint
(`fault_rows`), and how many fan run hours are there (`run_hours`)?

This script holds the Python loop and the pandas version, then times both as the data grows, and
times what it costs to copy a DataFrame into SQLite. Compare with day16_sql.py.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

TOL_PA = 25.0  # tolerance below setpoint, pascals
STEP_H = 5 / 60  # one row = 5 minutes, in hours
N_PARITY = 20_000  # rows for the answer both scripts compare
SIZES = lab.sizes([1_000, 10_000, 100_000, 1_000_000])

# 1. Data: deterministic synthetic history (the same rows in both scripts)
df = lab.synthetic_history(N_PARITY)
print(df.head(3).to_string(index=False))


# 2. Python side, version (a): a plain loop. The interpreter runs the body once per row.
def loop_answer(d):
    fault_rows = 0
    run_rows = 0
    for fan, static, sp in zip(d["fan_status"], d["duct_static"], d["duct_static_sp"], strict=True):
        if fan == 1:
            run_rows += 1
            if static < sp - TOL_PA:
                fault_rows += 1
    return {"fault_rows": fault_rows, "run_hours": run_rows * STEP_H}


# 3. Version (b): vectorized pandas. No loop in our code: each line is one whole-column operation.
def pandas_answer(d):
    running = d["fan_status"] == 1
    fault = running & (d["duct_static"] < d["duct_static_sp"] - TOL_PA)
    return {"fault_rows": int(fault.sum()), "run_hours": float(running.sum()) * STEP_H}


a, b = loop_answer(df), pandas_answer(df)
fault_run = pd.DataFrame([b])
print(f"\nloop   : {a}")
print(f"pandas : {b}")
print("loop and pandas agree:", a == b)

# 4. The same two numbers at every benchmark size (compared with the SQL script's)
by_size = pd.DataFrame([{"rows": n, **pandas_answer(lab.synthetic_history(n))} for n in SIZES])

# 5. Timing: grow the data, time only the computation (data built outside the timers)
timing, moving = [], []
for n in SIZES:
    d = lab.synthetic_history(n)
    reps = 3 if n <= 100_000 else 2
    t_loop = lab.best_time(lambda d=d: loop_answer(d), reps)
    t_pandas = lab.best_time(lambda d=d: pandas_answer(d), reps)
    timing.append({"rows": n, "loop_s": t_loop, "pandas_s": t_pandas})

    def insert(d=d):  # DataFrame -> SQLite: the cost of moving data *into* a database
        scratch = sqlite3.connect(":memory:")
        lab.to_sqlite(d, scratch, "h", index=["equipment_id", "ts"])
        scratch.close()

    moving.append(
        {
            "rows": n,
            "to_sql_s": lab.best_time(insert, 1 if n >= 1_000_000 else reps),
            "pandas_calc_s": t_pandas,
        }
    )

timing = pd.DataFrame(timing)
timing["loop/pandas"] = timing.loop_s / timing.pandas_s
timing["loop_us_per_row"] = timing.loop_s / timing.rows * 1e6
timing["pandas_us_per_row"] = timing.pandas_s / timing.rows * 1e6
moving = pd.DataFrame(moving)
moving["to_sql/calc"] = moving.to_sql_s / moving.pandas_calc_s

RESULTS = {"fault_run": fault_run, "fault_by_size": by_size}

print("\nfault rows and run hours (the loop and pandas give these):")
print(fault_run.round(3).to_string(index=False))
print(by_size.round(3).to_string(index=False))
print("\ntiming, seconds (times vary by machine; read the shape, not the digits):")
print(timing.to_string(index=False, float_format=lambda x: f"{x:,.4g}"))
print("\nwhat moving a DataFrame into SQLite costs, next to the pandas computation:")
print(moving.to_string(index=False, float_format=lambda x: f"{x:,.4g}"))
big = timing.iloc[-1]
print(f"\nobservation: at {int(big.rows):,} rows the loop is {big['loop/pandas']:.0f}x slower")
print(
    "observation: the loop is slowest at every size:", bool((timing.loop_s > timing.pandas_s).all())
)
print(
    "observation: copying into SQLite costs more than the calculation at every size:",
    bool((moving.to_sql_s > moving.pandas_calc_s).all()),
)
