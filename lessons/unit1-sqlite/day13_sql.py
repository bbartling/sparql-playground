"""Day 13, SQL: streaks ("gaps and islands") with three window-function steps.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day13_sql.py

The same computation as day13_pandas.py, done by SQLite on the same rows. SQLite does all the work;
pandas only turns the result rows into a table for printing.
Compare the printout with day13_pandas.py: the numbers should match.
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)

PARAMS = {
    "full_speed": 95.0,  # "at or near full speed" (percent)
    "confirm": 6,  # 6 rows x 5 min = 30 minutes
}

# 1. Load: both AHUs, the columns we need.
HISTORY_SQL = """
CREATE TEMP TABLE h AS
SELECT 'AHU_1' AS equipment_id, timestamp_utc, supply_fan_status, supply_fan_speed_pct FROM ahu_1
UNION ALL
SELECT 'AHU_2', timestamp_utc, supply_fan_status, supply_fan_speed_pct FROM ahu_2
"""

# 2. Fan runs. The three-step streak trick, once per CTE:
#    a) mark the rows where the value changes   b) running SUM of the marks = streak id
#    c) ROW_NUMBER inside each streak.  The first row has LAG NULL, so "= LAG" is NULL: ELSE 1.
FAN_ROWS_SQL = """
CREATE TEMP TABLE fan_rows AS
WITH marks AS (
  SELECT equipment_id, timestamp_utc, supply_fan_status,
         CASE WHEN supply_fan_status = LAG(supply_fan_status) OVER w THEN 0 ELSE 1 END AS new_streak
  FROM h
  WINDOW w AS (PARTITION BY equipment_id ORDER BY timestamp_utc)
), ids AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY timestamp_utc) AS run_id
  FROM marks
)
SELECT equipment_id, timestamp_utc, supply_fan_status, run_id,
       ROW_NUMBER() OVER (PARTITION BY equipment_id, run_id ORDER BY timestamp_utc) AS run_len
FROM ids
"""
FAN_RUNS_SQL = """
CREATE TEMP TABLE fan_runs AS
SELECT equipment_id, run_id,
       min(timestamp_utc) AS start_utc, max(timestamp_utc) AS end_utc,
       count(*) AS rows, count(*) * 5 / 60.0 AS hours
FROM fan_rows
WHERE supply_fan_status = 1
GROUP BY equipment_id, run_id
"""
# 3. The longest run per AHU (ties: the earliest): rank the runs, keep rank 1.
RUN_SUMMARY_SQL = """
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id ORDER BY rows DESC, start_utc) AS rank
  FROM fan_runs
)
SELECT equipment_id,
       (SELECT count(*) FROM fan_runs r WHERE r.equipment_id = k.equipment_id) AS runs,
       (SELECT avg(hours) FROM fan_runs r WHERE r.equipment_id = k.equipment_id) AS avg_run_hours,
       rows AS longest_rows, hours AS longest_hours, start_utc AS longest_start
FROM ranked k
WHERE rank = 1
ORDER BY equipment_id
"""

# 4. Confirmation: full speed for 6 rows in a row. Same trick on a 0/1 raw flag...
# 5. ...and the other route: SUM over the last 6 rows equals 6 only if all six were 1.
CONFIRM_SQL = """
CREATE TEMP TABLE confirm AS
WITH base AS (
  SELECT equipment_id, timestamp_utc,
         CASE WHEN supply_fan_status = 1 AND supply_fan_speed_pct >= :full_speed
              THEN 1 ELSE 0 END AS raw
  FROM h
), marks AS (
  SELECT *, CASE WHEN raw = LAG(raw) OVER w THEN 0 ELSE 1 END AS new_streak,
         SUM(raw) OVER (PARTITION BY equipment_id ORDER BY timestamp_utc
                        ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS last6,
         COUNT(*) OVER (PARTITION BY equipment_id ORDER BY timestamp_utc
                        ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS rows_in_window
  FROM base
  WINDOW w AS (PARTITION BY equipment_id ORDER BY timestamp_utc)
), ids AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY timestamp_utc) AS streak_id
  FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY timestamp_utc)
            AS streak_len
  FROM ids
)
SELECT equipment_id, timestamp_utc, raw, streak_id, streak_len,
       CASE WHEN raw = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS confirmed_streak,
       CASE WHEN rows_in_window = :confirm AND last6 = :confirm
            THEN 1 ELSE 0 END AS confirmed_window
FROM ranked
"""
CONFIRM_SUMMARY_SQL = """
SELECT equipment_id,
       sum(raw) AS raw_rows,
       sum(confirmed_streak) AS confirmed_rows_streak,
       sum(confirmed_window) AS confirmed_rows_window,
       count(DISTINCT CASE WHEN confirmed_streak = 1 THEN streak_id END) AS episodes
FROM confirm
GROUP BY equipment_id
ORDER BY equipment_id
"""

conn.execute(HISTORY_SQL)
conn.execute(FAN_ROWS_SQL)
conn.execute(FAN_RUNS_SQL)
conn.execute(CONFIRM_SQL, PARAMS)

fan_runs = pd.read_sql_query("SELECT * FROM fan_runs ORDER BY equipment_id, run_id", conn)
run_summary = pd.read_sql_query(RUN_SUMMARY_SQL, conn)
confirm = pd.read_sql_query("SELECT * FROM confirm ORDER BY equipment_id, timestamp_utc", conn)
confirm_summary = pd.read_sql_query(CONFIRM_SUMMARY_SQL, conn)

RESULTS = {
    "fan_runs": fan_runs,
    "run_summary": run_summary,
    "confirm_rows": confirm,
    "confirm_summary": confirm_summary,
}

print("Fan runs per AHU (status = 1 streaks):")
print(run_summary.round(2).to_string(index=False))
print("\nFull speed (>= 95 %) for 6 rows in a row, by streak id and by rolling sum:")
print(confirm_summary.to_string(index=False))
