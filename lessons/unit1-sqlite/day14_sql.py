"""Day 14, SQL: FC1 (duct static too low while the fan runs) on both AHUs.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day14_sql.py

The same computation as day14_pandas.py, done by SQLite on the same rows. SQLite does all the work;
pandas only turns the result rows into a table for printing.
Compare the printout with day14_pandas.py: the numbers should match.
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
    "pa_per_inh2o": 249.08891,  # the historian logged inches of water; fault math is SI (pascals)
    "tol": 25.0,  # how far below setpoint counts as a fault (~0.1 inH2O)
    "confirm": 2,  # 2 rows x 5 min = 10 minutes before a fault counts
}

# One query, one CTE per step. ahu_1 and ahu_2 are the CSVs loaded as tables, same column names.
FC1_SQL = """
CREATE TEMP TABLE fc1 AS
WITH h AS (                                   -- 1. load: both AHUs, the columns FC1 needs
  SELECT 'AHU_1' AS equipment_id, timestamp_utc, supply_fan_status, da_p_inwc, da_p_setpoint_inwc
  FROM ahu_1
  UNION ALL
  SELECT 'AHU_2', timestamp_utc, supply_fan_status, da_p_inwc, da_p_setpoint_inwc
  FROM ahu_2
), si AS (                                    -- 2. SI units
  SELECT equipment_id, timestamp_utc, supply_fan_status,
         da_p_inwc * :pa_per_inh2o          AS duct_static_pa,
         da_p_setpoint_inwc * :pa_per_inh2o AS duct_static_sp_pa
  FROM h
), base AS (                                  -- 3. gate + raw fault
  SELECT equipment_id, timestamp_utc,
         CASE WHEN supply_fan_status = 1 AND duct_static_pa < duct_static_sp_pa - :tol
              THEN 1 ELSE 0 END AS raw_fault
  FROM si
), marks AS (                                 -- 4a. a new streak starts where raw_fault changes
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER w THEN 0 ELSE 1 END AS new_streak
  FROM base
  WINDOW w AS (PARTITION BY equipment_id ORDER BY timestamp_utc)
), streaks AS (                               -- 4b. running sum of starts numbers the streaks
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY timestamp_utc) AS streak_id
  FROM marks
), ranked AS (                                -- 4c. row number inside each streak
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY timestamp_utc)
            AS streak_len
  FROM streaks
)
SELECT equipment_id, timestamp_utc, raw_fault, streak_id,
       CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
FROM ranked
"""
conn.execute(FC1_SQL, PARAMS)
conn.execute("CREATE INDEX temp.fc1_eq_ts ON fc1 (equipment_id, timestamp_utc)")

SUMMARY_SQL = """
SELECT equipment_id,                          -- 5. rows x 5 minutes = hours
       sum(raw_fault) * 5 / 60.0 AS raw_fault_h,
       sum(fault) * 5 / 60.0     AS confirmed_fault_h,
       count(DISTINCT CASE WHEN fault = 1 THEN streak_id END) AS episodes
FROM fc1
GROUP BY equipment_id
ORDER BY equipment_id
"""

OPENFDD_SQL = """
SELECT replace(hvac_system, 'bld_50_', '') AS equipment_id,
       count(*) AS episodes, sum(duration_min) / 60 AS hours
FROM fdd_events
WHERE rule_name = 'fc1'
GROUP BY equipment_id
"""

# 6. For each Open-FDD episode, does at least one of our confirmed fault rows fall inside it?
# The timestamps are ISO text in one format, so BETWEEN on text compares them in time order.
OVERLAP_SQL = """
SELECT count(*) AS openfdd_episodes,
       sum(EXISTS (SELECT 1 FROM fc1 f
                   WHERE f.equipment_id = replace(e.hvac_system, 'bld_50_', '')
                     AND f.fault = 1
                     AND f.timestamp_utc BETWEEN e.start_time_utc AND e.end_time_utc))
         AS also_found_by_us
FROM fdd_events e
WHERE e.rule_name = 'fc1'
"""

fc1 = pd.read_sql_query("SELECT * FROM fc1 ORDER BY equipment_id, timestamp_utc", conn)
summary = pd.read_sql_query(SUMMARY_SQL, conn)
openfdd = pd.read_sql_query(OPENFDD_SQL, conn)
overlap = pd.read_sql_query(OVERLAP_SQL, conn)

RESULTS = {"fc1_per_row": fc1, "fc1_summary": summary, "openfdd_fc1": openfdd, "overlap": overlap}

print("FC1 per AHU (hours, episodes):")
print(summary.round(2).to_string(index=False))
print("\nOpen-FDD's FC1 episodes for the same data:")
print(openfdd.round(1).to_string(index=False))
print("\nOpen-FDD episodes that contain at least one of our confirmed fault rows:")
print(overlap.to_string(index=False))
