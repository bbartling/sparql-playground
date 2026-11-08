"""Day 20, SQL side: Day 14's FC1 confirmation streaks as SQLite window functions, at scale.

    uv run python lessons/unit2-python/day20_sql.py

The rule is Day 14's: raw fault = fan running and duct static more than 25 Pa below setpoint; a
fault is confirmed once the raw fault has held for 2 consecutive rows. SQLite does it with window
functions: LAG marks where the value changes, a running SUM numbers the streaks, ROW_NUMBER counts
the rows inside each streak. It sorts and partitions, then makes several window passes.

Timed on data that grows 10x per step (loading is setup, timed apart from the query), plus the "stop
early" experiment (SQL has no early exit: the window query computes every row first) and the Week 4
challenge (longest confirmed episode per AHU, as GROUP BY the streak id). Same synthetic rows as
day20_pandas.py.
"""

import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

PARAMS = {"tol": 25.0, "confirm": 2}  # pascals; rows (10 minutes at 5-minute spacing)
SIZES = lab.sizes([1_000, 10_000, 100_000, 1_000_000])
N_PARITY = 5_000  # rows per AHU for the per-row result
N_FIRST = 20_000 if lab.QUICK else 200_000  # rows for the stop-early experiment
N_CHALLENGE = 5_000 if lab.QUICK else 20_000  # rows per AHU for the challenge

# One CTE chain; the queries below add a final SELECT to it.
RULE_SQL = """
WITH base AS (                                -- gate + raw fault
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol
              THEN 1 ELSE 0 END AS raw_fault
  FROM h
), marks AS (                                 -- a new streak starts where raw_fault changes
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                 THEN 0 ELSE 1 END AS new_streak
  FROM base
), streaks AS (                               -- running sum of starts numbers the streaks
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id
  FROM marks
), ranked AS (                                -- row number inside each streak
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len
  FROM streaks
), per_row AS (
  SELECT equipment_id, ts, streak_id,
         CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
  FROM ranked
)
"""
# streak_id restarts at 1 for each AHU, so episodes are counted per (AHU, streak)
PER_ROW_SQL = RULE_SQL + "SELECT equipment_id, ts, fault FROM per_row ORDER BY equipment_id, ts"
TOTALS_SQL = (
    RULE_SQL
    + """
SELECT COALESCE(SUM(fault), 0) AS fault_rows,
       COUNT(DISTINCT CASE WHEN fault = 1 THEN equipment_id || ':' || streak_id END) AS episodes
FROM per_row
"""
)
FIRST_SQL = RULE_SQL + "SELECT MIN(ts) AS first_fault_ts FROM per_row WHERE fault = 1"

# Week 4 challenge: GROUP BY the streak id, keep the confirmed ones, take the MAX per AHU
LONGEST_SQL = """
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol
              THEN 1 ELSE 0 END AS raw_fault
  FROM h
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                 THEN 0 ELSE 1 END AS new_streak
  FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id
  FROM marks
), episodes AS (
  SELECT equipment_id, streak_id, COUNT(*) AS rows_in_streak
  FROM streaks WHERE raw_fault = 1
  GROUP BY equipment_id, streak_id HAVING COUNT(*) >= :confirm
)
SELECT equipment_id, MAX(rows_in_streak) AS longest_rows, MAX(rows_in_streak) * 5.0 AS longest_min
FROM episodes GROUP BY equipment_id ORDER BY equipment_id
"""


def make(n, equips=1):
    """n rows per AHU of synthetic history in an in-memory table `h` with an index. Setup."""
    mem = sqlite3.connect(":memory:")
    lab.to_sqlite(lab.synthetic_history(n, equips=equips), mem, "h", index=["equipment_id", "ts"])
    return mem


def query(mem, sql):
    return pd.read_sql_query(sql, mem, params=PARAMS)


# 1. Per-row faults on two AHUs (so the PARTITION BY matters)
mem2 = make(N_PARITY, equips=2)
per_row = query(mem2, PER_ROW_SQL)
print(f"two AHUs x {N_PARITY:,} rows: {int(per_row.fault.sum())} confirmed fault rows")

# 2. The showdown: load once per size (timed apart), then time the window query (one AHU)
timing, totals = [], []
for n in SIZES:
    started = time.perf_counter()
    mem = make(n)
    t_load = time.perf_counter() - started
    reps = 3 if n <= 100_000 else 1
    totals.append({"rows": n, **query(mem, TOTALS_SQL).iloc[0].astype(int).to_dict()})
    timing.append(
        {
            "rows": n,
            "sql_load": t_load,
            "sql_window": lab.best_time(lambda mem=mem: query(mem, TOTALS_SQL), reps),
        }
    )
    mem.close()
totals = pd.DataFrame(totals)
t = pd.DataFrame(timing).set_index("rows")
growth = (t / t.shift(1)).dropna()

# 3. Stop early: SQL has no early exit. The window functions compute every row's state, so even a
#    MIN(ts) over the faults takes as long as the whole query (and LIMIT 1 would not change that).
memf = make(N_FIRST)
first_fault = query(memf, FIRST_SQL)
t_first = lab.best_time(lambda: query(memf, FIRST_SQL))
t_full = lab.best_time(lambda: query(memf, TOTALS_SQL))

# 4. Week 4 challenge: longest confirmed episode per AHU
memc = make(N_CHALLENGE, equips=2)
longest = query(memc, LONGEST_SQL)

RESULTS = {
    "per_row": per_row,
    "totals_by_size": totals,
    "first_fault": first_fault,
    "longest_episode": longest,
}

print("\nFC1 totals at every size (the pandas script finds the same numbers):")
print(totals.to_string(index=False))
print("\nseconds (times vary by machine; read the shape, not the digits)")
print(t.map(lambda x: f"{x:,.4g}").to_string())
print("\ngrowth: time at this size / time at the previous (10x smaller) size")
print(growth.round(1).to_string())
print(f"\nFirst confirmed fault in {N_FIRST:,} rows: ts {first_fault.first_fault_ts[0]}")
print(f"  SQL, MIN(ts) over the faults   {t_first:.4f} s")
print(f"  SQL, totals query              {t_full:.4f} s")
print(f"\nLongest confirmed episode per AHU ({N_CHALLENGE:,} rows each):")
print(longest.to_string(index=False))
big = t.iloc[-1]
print(f"\nobservation: at {t.index[-1]:,} rows the window query takes {big['sql_window']:.3f} s")
