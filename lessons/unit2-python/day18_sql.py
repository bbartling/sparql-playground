"""Day 18, SQL side: FC1 with forward sample-and-hold, a gap limit and coverage, on data with holes.

    uv run python lessons/unit2-python/day18_sql.py

The same computation as day18_pandas.py on the same synthetic gappy rows (loaded into in-memory
SQLite as setup). Same shape as Open-FDD's cmd1_fan_mismatch.sql, in SQLite's dialect:
LEAD gives the next timestamp, so `held_seconds = next_ts - ts`; a gap longer than MAX_GAP_HOURS is
held 0 and breaks the streak; a fault confirms after CONFIRM_SECONDS of elapsed time (a running SUM
of held_seconds inside the streak); coverage is held seconds over the window.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

PARAMS = {
    "tol": 25.0,  # how far below setpoint counts as a fault, pascals
    "max_gap_s": 1.0 * 3600,  # MAX_GAP_HOURS = 1: a longer silence is "unknown"
    "confirm_s": 600,  # 10 minutes, the same as Day 14's two 5-minute rows
}
N = 4_000  # rows per AHU before drops: about 14 days

# 1. Data with holes (same recipe as the pandas script): 3% of rows dropped at random, plus one
#    long outage on AHU_1 (100 rows, about 8 hours) inside its weak-fan window. Setup.
raw_df = lab.synthetic_history(N, equips=2, gap_prob=0.03)
T0 = int(raw_df.ts.min())
outage = (raw_df.equipment_id == "AHU_1") & raw_df.ts.between(T0 + 1560 * 300, T0 + 1659 * 300)
gappy = raw_df[~outage].sort_values(["equipment_id", "ts"]).reset_index(drop=True)
conn = sqlite3.connect(":memory:")
lab.to_sqlite(gappy, conn, "gap_h", index=["equipment_id", "ts"])
print(conn.execute("SELECT count(*) FROM gap_h").fetchone()[0], "rows in gap_h")

# 2. One query returns every row's state; one CTE per step.
ROW_SQL = """
WITH base AS (                                -- gate + raw fault
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol
              THEN 1 ELSE 0 END AS raw_fault
  FROM gap_h
), stepped AS (                               -- LEAD: seconds until the next reading
  SELECT *, LEAD(ts) OVER (PARTITION BY equipment_id ORDER BY ts) - ts AS dt_seconds
  FROM base
), elapsed_hold AS (                          -- sample-and-hold, with the gap limit
  SELECT *,
         CASE WHEN dt_seconds IS NULL OR dt_seconds <= 0 OR dt_seconds > :max_gap_s
              THEN 0.0 ELSE dt_seconds END AS held_seconds,
         CASE WHEN dt_seconds > :max_gap_s THEN 1 ELSE 0 END AS gap_after
  FROM stepped
), lagged AS (                                -- a streak breaks on a change or after a gap
  SELECT *,
         CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                   AND COALESCE(LAG(gap_after) OVER (PARTITION BY equipment_id ORDER BY ts), 0) = 0
              THEN 0 ELSE 1 END AS is_new_streak
  FROM elapsed_hold
), grp AS (
  SELECT *, SUM(is_new_streak) OVER (PARTITION BY equipment_id ORDER BY ts
                                     ROWS UNBOUNDED PRECEDING) AS streak_id
  FROM lagged
), ranked AS (                                -- elapsed time inside each streak
  SELECT *, SUM(held_seconds) OVER (PARTITION BY equipment_id, streak_id ORDER BY ts
                                    ROWS UNBOUNDED PRECEDING) AS streak_elapsed
  FROM grp
)
SELECT equipment_id, ts, raw_fault, held_seconds, gap_after, streak_id, streak_elapsed,
       CASE WHEN raw_fault = 1 AND streak_elapsed >= :confirm_s THEN 1 ELSE 0 END AS confirmed
FROM ranked
"""

# 3. Summary: fault hours, covered hours and coverage per AHU
SUMMARY_SQL = f"""
SELECT equipment_id,
       COUNT(*) AS rows,
       SUM(gap_after) AS long_gaps,
       SUM(CASE WHEN confirmed = 1 THEN held_seconds ELSE 0.0 END) / 3600.0 AS fault_hours,
       SUM(held_seconds) / 3600.0 AS covered_hours,
       (MAX(ts) - MIN(ts)) / 3600.0 AS window_hours,
       SUM(held_seconds) / (MAX(ts) - MIN(ts)) AS coverage
FROM ({ROW_SQL})
GROUP BY equipment_id
ORDER BY equipment_id
"""

# 4. The wrong way: Day 14's row-counting version on the same gappy table
NAIVE_SQL = """
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END
           AS raw_fault
  FROM gap_h
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                 THEN 0 ELSE 1 END AS new_streak
  FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len
  FROM streaks
)
SELECT equipment_id, SUM(raw_fault = 1 AND streak_len >= 2) * 5 / 60.0 AS naive_fault_hours
FROM ranked GROUP BY equipment_id ORDER BY equipment_id
"""


def run(sql, **override):
    return pd.read_sql_query(sql, conn, params={**PARAMS, **override})


rows = run(ROW_SQL)
summary = run(SUMMARY_SQL)
naive = run(NAIVE_SQL)

# 5. Try-it variants: a 12-hour gap limit, and confirming over 1 hour
summary_12h = run(SUMMARY_SQL, max_gap_s=12.0 * 3600)
summary_confirm_1h = run(SUMMARY_SQL, confirm_s=3600)

RESULTS = {
    "rows": rows,
    "summary": summary,
    "naive_fault_hours": naive,
    "summary_12h_limit": summary_12h,
    "summary_confirm_1h": summary_confirm_1h,
}

print("\nGap-aware summary:")
print(summary.round(3).to_string(index=False))
print("\nThe one row with gap_after = 1 per AHU that has an outage:")
print(rows[rows.gap_after == 1].round(1).to_string(index=False))

cmp = naive.merge(summary[["equipment_id", "fault_hours"]], on="equipment_id")
cmp["difference_h"] = cmp.fault_hours - cmp.naive_fault_hours
print("\nRow counting (Day 14) vs gap-aware, fault hours:")
print(cmp.round(2).to_string(index=False))

print("\nTry-it variants (fault hours / coverage):")
print("MAX_GAP_HOURS = 12:")
print(
    summary_12h[["equipment_id", "long_gaps", "fault_hours", "coverage"]]
    .round(3)
    .to_string(index=False)
)
print("CONFIRM_SECONDS = 3600:")
print(summary_confirm_1h[["equipment_id", "fault_hours"]].round(2).to_string(index=False))
