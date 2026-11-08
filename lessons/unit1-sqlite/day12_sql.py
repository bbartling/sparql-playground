"""Day 12, SQL: window functions -- LAG/LEAD, a 1-hour rolling mean, and fan starts and stops.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day12_sql.py

The same computation as day12_pandas.py, done by SQLite on the same rows. SQLite does all the work;
pandas only turns the result rows into a table for printing.
Compare the printout with day12_pandas.py: the numbers should match.
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

# the historian logged inches of water; the math is SI (pascals)
PARAMS = {"pa_per_inh2o": 249.08891}

# One CTE per step. The window is 12 rows x 5 min = 1 hour; LEAD 3 looks 15 minutes ahead.
WINDOWS_SQL = """
CREATE TEMP TABLE windows AS
WITH h AS (                                   -- 1. load: both AHUs, the columns we need
  SELECT 'AHU_1' AS equipment_id, timestamp_utc, supply_fan_status, da_p_inwc FROM ahu_1
  UNION ALL
  SELECT 'AHU_2', timestamp_utc, supply_fan_status, da_p_inwc FROM ahu_2
), si AS (                                    -- 2. SI units
  SELECT equipment_id, timestamp_utc, supply_fan_status,
         da_p_inwc * :pa_per_inh2o AS duct_static_pa
  FROM h
), w AS (                                     -- 3-5. neighbours, rolling mean, previous fan status
  SELECT equipment_id, timestamp_utc, supply_fan_status, duct_static_pa,
         LAG(duct_static_pa)     OVER ord AS static_prev_pa,
         LEAD(duct_static_pa)    OVER ord AS static_next_pa,
         LEAD(duct_static_pa, 3) OVER ord AS static_ahead_pa,
         AVG(duct_static_pa) OVER (PARTITION BY equipment_id ORDER BY timestamp_utc
                                   ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS static_1h_mean_pa,
         LAG(supply_fan_status)  OVER ord AS fan_prev
  FROM si
  WINDOW ord AS (PARTITION BY equipment_id ORDER BY timestamp_utc)
)
SELECT equipment_id, timestamp_utc, supply_fan_status, duct_static_pa, static_prev_pa,
       static_next_pa, static_ahead_pa,
       duct_static_pa - static_prev_pa AS static_step_pa,
       static_1h_mean_pa,
       CASE WHEN supply_fan_status = 1 AND fan_prev = 0 THEN 1 ELSE 0 END AS fan_start,
       CASE WHEN supply_fan_status = 0 AND fan_prev = 1 THEN 1 ELSE 0 END AS fan_stop
FROM w
"""
conn.execute(WINDOWS_SQL, PARAMS)

SUMMARY_SQL = """
SELECT equipment_id,                          -- 6. one line per AHU
       sum(fan_start) AS fan_starts,
       sum(fan_stop)  AS fan_stops,
       max(static_1h_mean_pa) AS max_static_1h_mean_pa,
       min(CASE WHEN fan_start = 1 THEN timestamp_utc END) AS first_start,
       avg(CASE WHEN fan_start = 1 THEN static_ahead_pa END) AS avg_static_15min_after_start_pa
FROM windows
GROUP BY equipment_id
ORDER BY equipment_id
"""
EVENTS_SQL = """
SELECT equipment_id, timestamp_utc, fan_start, fan_stop
FROM windows
WHERE fan_start = 1 OR fan_stop = 1
ORDER BY equipment_id, timestamp_utc
"""

windows = pd.read_sql_query("SELECT * FROM windows ORDER BY equipment_id, timestamp_utc", conn)
summary = pd.read_sql_query(SUMMARY_SQL, conn)
events = pd.read_sql_query(EVENTS_SQL, conn)

RESULTS = {"windows": windows, "fan_summary": summary, "fan_events": events}

print("Fan cycling per AHU (duct static in Pa):")
print(summary.round(2).to_string(index=False))
print("\nFirst 6 fan events on AHU_1 (start=1 / stop=1):")
print(events[events["equipment_id"] == "AHU_1"].head(6).to_string(index=False))
sample = (
    windows[(windows["equipment_id"] == "AHU_1") & (windows["fan_start"] == 1)].head(1).index[0]
)
print("\nAround the first AHU_1 fan start:")
cols = [
    "timestamp_utc",
    "supply_fan_status",
    "duct_static_pa",
    "static_prev_pa",
    "static_1h_mean_pa",
]
print(windows.loc[sample - 2 : sample + 3, cols].round(1).to_string(index=False))
