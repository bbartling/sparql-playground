"""Day 15, SQL: data quality before you trust a rule, then the Unit 1 challenge (a DAT rule).

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day15_sql.py

The same computation as day15_pandas.py, done by SQLite on the same rows. SQLite does all the work;
pandas only turns the result rows into a table for printing.
Compare the printout with day15_pandas.py: the numbers should match.
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
    "pa_per_inh2o": 249.08891,  # the historian logged inches of water; the math is SI (pascals)
    "flat_rows": 12,  # an identical value for 12 rows x 5 min = 1 hour, fan running, is suspicious
    "tol": 2.78,  # |discharge - setpoint| above this is a fault (5 degF is 2.78 degC)
    "confirm": 6,  # 6 rows x 5 min = 30 minutes
    "step_s": 300,  # the historian logs every 5 minutes
    "zero_f_in_c": (0 - 32.0) * 5.0 / 9.0,  # what a dropout looks like after conversion: -17.777...
    "temp_lo": -40.0,  # a sensor's physical range
    "temp_hi": 60.0,
    "static_lo": 0.0,
    "static_hi": 1500.0,
    "speed_lo": 0.0,
    "speed_hi": 100.0,
}

# One query, one CTE per step. ahu_1 and ahu_2 are the CSVs loaded as tables, same column names.
QUALITY_SQL = """
CREATE TEMP TABLE q AS
WITH h AS (                                   -- 1. load: both AHUs, the columns we need
  SELECT 'AHU_1' AS equipment_id, timestamp_utc, supply_fan_status, supply_fan_speed_pct, da_p_inwc,
         discharge_air_temp_f, dat_reset_f, mixed_air_temp_f, return_air_temp_f, outside_air_temp_f
  FROM ahu_1
  UNION ALL
  SELECT 'AHU_2', timestamp_utc, supply_fan_status, supply_fan_speed_pct, da_p_inwc,
         discharge_air_temp_f, dat_reset_f, mixed_air_temp_f, return_air_temp_f, outside_air_temp_f
  FROM ahu_2
), si AS (                                    -- 2. SI units (raw degF stays for the dropout test)
  SELECT h.*,
         (discharge_air_temp_f - 32.0) * 5.0 / 9.0 AS dat_c,
         (dat_reset_f - 32.0) * 5.0 / 9.0          AS dat_sp_c,
         (mixed_air_temp_f - 32.0) * 5.0 / 9.0     AS mat_c,
         (return_air_temp_f - 32.0) * 5.0 / 9.0    AS rat_c,
         (outside_air_temp_f - 32.0) * 5.0 / 9.0   AS oat_c,
         da_p_inwc * :pa_per_inh2o                 AS duct_static_pa
  FROM h
), flags AS (                                 -- 3-5. quality flags; 6a. flat marks; 7. time step
  SELECT *,
         CASE WHEN discharge_air_temp_f = 0 OR mixed_air_temp_f = 0 OR return_air_temp_f = 0
              THEN 1 ELSE 0 END AS dropout,
         CASE WHEN supply_fan_status = 1 AND dat_reset_f = 0 THEN 1 ELSE 0 END AS sp_zero,
         CASE WHEN dat_c NOT BETWEEN :temp_lo AND :temp_hi
                OR mat_c NOT BETWEEN :temp_lo AND :temp_hi
                OR rat_c NOT BETWEEN :temp_lo AND :temp_hi
                OR oat_c NOT BETWEEN :temp_lo AND :temp_hi
                OR duct_static_pa NOT BETWEEN :static_lo AND :static_hi
                OR supply_fan_speed_pct NOT BETWEEN :speed_lo AND :speed_hi
              THEN 1 ELSE 0 END AS out_of_range,
         CASE WHEN discharge_air_temp_f = LAG(discharge_air_temp_f) OVER w
              THEN 0 ELSE 1 END AS new_flat,
         unixepoch(timestamp_utc) AS epoch_s,
         unixepoch(timestamp_utc) - LAG(unixepoch(timestamp_utc)) OVER w AS step_s
  FROM si
  WINDOW w AS (PARTITION BY equipment_id ORDER BY timestamp_utc)
), flat_ids AS (                              -- 6b. running sum of marks = streak id
  SELECT *, SUM(new_flat) OVER (PARTITION BY equipment_id ORDER BY timestamp_utc) AS flat_id
  FROM flags
), flat AS (                                  -- 6c. row in streak; streak size and fan rows
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY equipment_id, flat_id ORDER BY timestamp_utc) AS flat_len,
         COUNT(*)               OVER (PARTITION BY equipment_id, flat_id) AS island_rows,
         SUM(supply_fan_status) OVER (PARTITION BY equipment_id, flat_id) AS island_running
  FROM flat_ids
)
SELECT equipment_id, timestamp_utc, supply_fan_status, dat_c, dat_sp_c, mat_c, rat_c, oat_c,
       duct_static_pa,
       dropout, sp_zero, out_of_range, flat_id, flat_len,
       CASE WHEN island_rows >= :flat_rows AND island_running = island_rows
            THEN 1 ELSE 0 END AS flatline,
       step_s, epoch_s, substr(timestamp_utc, 1, 7) AS month
FROM flat
"""

FLAT_EPISODES_SQL = """
SELECT equipment_id, flat_id, min(timestamp_utc) AS start_utc, max(flat_len) AS rows,
       min(dat_c) AS value_c
FROM q
WHERE flatline = 1
GROUP BY equipment_id, flat_id
ORDER BY equipment_id, flat_id
"""

# 8. One line of checks per AHU.
CHECKS_SQL = """
SELECT equipment_id,
       sum(dropout) AS dropout_rows,
       sum(sp_zero) AS sp_zero_rows,
       sum(out_of_range) AS out_of_range_rows,
       sum(flatline) AS flatline_rows,
       sum(CASE WHEN step_s <> :step_s THEN 1 ELSE 0 END) AS step_gaps,
       max(step_s) AS max_step_s,
       (SELECT count(DISTINCT f.flat_id) FROM q f
         WHERE f.equipment_id = q.equipment_id AND f.flatline = 1) AS flat_episodes,
       sum(CASE WHEN dat_c = -17.78 THEN 1 ELSE 0 END) AS dat_eq_minus_17_78,
       sum(CASE WHEN abs(dat_c - :zero_f_in_c) < 0.01 THEN 1 ELSE 0 END)
         AS dat_within_0_01_of_zero_f
FROM q
GROUP BY equipment_id
ORDER BY equipment_id
"""

# 9. Coverage per AHU per month: rows present vs rows expected, first to last timestamp.
COVERAGE_SQL = """
SELECT equipment_id, month,
       count(*) AS rows,
       CAST(sum(supply_fan_status) AS INTEGER) AS running_rows,
       sum(dropout) AS dropout_rows,
       sum(sp_zero) AS sp_zero_rows,
       sum(flatline) AS flat_rows,
       (max(epoch_s) - min(epoch_s)) / :step_s + 1 AS expected_rows,
       100.0 * count(*) / ((max(epoch_s) - min(epoch_s)) / :step_s + 1) AS coverage_pct
FROM q
GROUP BY equipment_id, month
ORDER BY equipment_id, month
"""

# 10. Challenge: |discharge - setpoint| > 2.78 degC while running, confirmed for 6 rows.
# Two variants: "ungated" trusts every row; "gated" skips dropouts and the missing (0) setpoint.
DAT_SQL = """
CREATE TEMP TABLE dat_rows AS
WITH base AS (
  SELECT equipment_id, timestamp_utc, month, supply_fan_status, dropout, sp_zero,
         abs(dat_c - dat_sp_c) AS err_c
  FROM q
), v AS (
  SELECT 'ungated' AS variant, equipment_id, timestamp_utc, month,
         CASE WHEN supply_fan_status = 1 AND err_c > :tol THEN 1 ELSE 0 END AS raw_fault
  FROM base
  UNION ALL
  SELECT 'gated', equipment_id, timestamp_utc, month,
         CASE WHEN supply_fan_status = 1 AND dropout = 0 AND sp_zero = 0 AND err_c > :tol
              THEN 1 ELSE 0 END
  FROM base
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER w THEN 0 ELSE 1 END AS new_streak
  FROM v
  WINDOW w AS (PARTITION BY variant, equipment_id ORDER BY timestamp_utc)
), ids AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY variant, equipment_id ORDER BY timestamp_utc)
            AS streak_id
  FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY variant, equipment_id, streak_id ORDER BY timestamp_utc)
            AS streak_len
  FROM ids
)
SELECT variant, equipment_id, timestamp_utc, month, raw_fault, streak_id,
       CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
FROM ranked
"""
DAT_MONTH_SQL = """
SELECT equipment_id, month,
       sum(CASE WHEN variant = 'ungated' AND fault = 1 THEN 1 ELSE 0 END) * 5 / 60.0
         AS ungated_fault_h,
       sum(CASE WHEN variant = 'gated' AND fault = 1 THEN 1 ELSE 0 END) * 5 / 60.0
         AS gated_fault_h
FROM dat_rows
GROUP BY equipment_id, month
ORDER BY equipment_id, month
"""

conn.execute(QUALITY_SQL, PARAMS)
conn.execute(DAT_SQL, PARAMS)

quality = pd.read_sql_query(
    "SELECT equipment_id, timestamp_utc, supply_fan_status, dat_c, dat_sp_c, mat_c, rat_c, oat_c,"
    " duct_static_pa, dropout, sp_zero, out_of_range, flat_len, flatline, step_s"
    " FROM q ORDER BY equipment_id, timestamp_utc",
    conn,
)
flat_episodes = pd.read_sql_query(FLAT_EPISODES_SQL, conn)
checks = pd.read_sql_query(CHECKS_SQL, conn, params=PARAMS)
coverage = pd.read_sql_query(COVERAGE_SQL, conn, params=PARAMS)
dat_rows = pd.read_sql_query(
    "SELECT equipment_id, timestamp_utc, variant, raw_fault, streak_id, fault"
    " FROM dat_rows ORDER BY variant, equipment_id, timestamp_utc",
    conn,
)
dat_month = pd.read_sql_query(DAT_MONTH_SQL, conn)

RESULTS = {
    "quality_rows": quality,
    "checks": checks,
    "flat_episodes": flat_episodes,
    "coverage": coverage,
    "dat_rows": dat_rows,
    "dat_month": dat_month,
}

print("Quality checks per AHU:")
print(checks.round(2).T.to_string(header=False))
print("\nThe 7 dropout rows on AHU_1 (every sensor reads 0 degF = -17.78 degC):")
dropped = quality[(quality["equipment_id"] == "AHU_1") & (quality["dropout"] == 1)]
print(dropped[["timestamp_utc", "dat_c", "dat_sp_c"]].round(2).to_string(index=False))
print("\nCoverage per AHU per month (AHU_1):")
print(coverage[coverage["equipment_id"] == "AHU_1"].round(1).to_string(index=False))
print("\nChallenge: DAT rule fault hours per AHU per month (ungated vs gated):")
print(dat_month.round(2).to_string(index=False))
print("\nTotals:")
print(
    dat_month.groupby("equipment_id")[["ungated_fault_h", "gated_fault_h"]]
    .sum()
    .round(2)
    .to_string()
)
