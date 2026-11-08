"""Day 16, SQL side: one answer as a single SQL aggregate on SQLite.

    uv run python lessons/unit2-python/day16_sql.py

The same question as day16_pandas.py on the same synthetic rows: how many 5-minute rows have the fan
running with duct static more than 25 Pa below setpoint (`fault_rows`), and how many fan run hours
are there (`run_hours`)? The rows are loaded into an in-memory SQLite table first; loading is setup
(timed on its own), the aggregate is the computation. Compare with day16_pandas.py.
"""

import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

PARAMS = {
    "tol": 25.0,  # tolerance below setpoint, pascals
    "step_h": 5 / 60,  # one row = 5 minutes, in hours
}
N_PARITY = 20_000  # rows for the answer both scripts compare
SIZES = lab.sizes([1_000, 10_000, 100_000, 1_000_000])

# The loop moves inside the database; only one row comes back.
# SUM(fan_status = 1) works because a comparison is 0 or 1 in SQLite.
AGG_SQL = """
SELECT SUM(CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END)
         AS fault_rows,
       SUM(fan_status = 1) * :step_h AS run_hours
FROM h
"""


def make(n):
    """n rows of synthetic history in an in-memory table `h`, with an index. Setup, not compared."""
    mem = sqlite3.connect(":memory:")
    lab.to_sqlite(lab.synthetic_history(n), mem, "h", index=["equipment_id", "ts"])
    return mem


# 1. Data: the same synthetic history, loaded into SQLite
conn = make(N_PARITY)
print(pd.read_sql_query("SELECT * FROM h LIMIT 3", conn).to_string(index=False))

# 2. The aggregate (version (c))
fault_run = pd.read_sql_query(AGG_SQL, conn, params=PARAMS)

# 3. The same two numbers at every benchmark size
by_size = []
for n in SIZES:
    mem = make(n)
    by_size.append({"rows": n, **pd.read_sql_query(AGG_SQL, mem, params=PARAMS).iloc[0].to_dict()})
    mem.close()
by_size = pd.DataFrame(by_size).astype({"rows": "int64", "fault_rows": "int64"})

# 4. Timing: load once per size (timed separately), then time only the aggregate and the copy out
timing = []
for n in SIZES:
    started = time.perf_counter()  # setup: build the table and its index, timed on its own
    mem = make(n)
    t_load = time.perf_counter() - started
    reps = 3 if n <= 100_000 else 2
    timing.append(
        {
            "rows": n,
            "load_s": t_load,
            "sql_agg_s": lab.best_time(
                lambda mem=mem: mem.execute(AGG_SQL, PARAMS).fetchone(), reps
            ),
            # the cost of moving the whole table *out* into a DataFrame (no computation at all)
            "read_sql_s": lab.best_time(
                lambda mem=mem: pd.read_sql_query("SELECT * FROM h", mem),
                1 if n >= 1_000_000 else reps,
            ),
        }
    )
    mem.close()
timing = pd.DataFrame(timing)
timing["read_sql/agg"] = timing.read_sql_s / timing.sql_agg_s
timing["agg_us_per_row"] = timing.sql_agg_s / timing.rows * 1e6

RESULTS = {"fault_run": fault_run, "fault_by_size": by_size}

print("\nfault rows and run hours (the SQL aggregate gives these):")
print(fault_run.round(3).to_string(index=False))
print(by_size.round(3).to_string(index=False))
print("\ntiming, seconds (times vary by machine; read the shape, not the digits):")
print(timing.to_string(index=False, float_format=lambda x: f"{x:,.4g}"))
print("\nthe aggregate vs. getting the rows out (compare pandas_calc_s in day16_pandas.py):")
print(
    timing[["rows", "sql_agg_s", "read_sql_s", "read_sql/agg"]].to_string(
        index=False, float_format=lambda x: f"{x:,.4g}"
    )
)
print(
    "\nobservation: copying the table into a DataFrame costs more than the SQL aggregate:",
    bool((timing.read_sql_s > timing.sql_agg_s).all()),
)
