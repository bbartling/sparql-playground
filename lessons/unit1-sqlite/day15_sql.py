# Day 15 (SQL): data-quality checks, then the Unit 1 challenge: a discharge air temp rule.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day15_sql.py

import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

settings = {
    "flat_rows": 12,  # the same value for 12 rows x 5 min = 1 hour, fan running, is suspicious
    "tolerance_c": 2.78,  # more than this far from setpoint is a fault (5 degF = 2.78 degC)
    "confirm_rows": 6,  # 6 rows x 5 min = 30 minutes
    "temp_min_c": -40,  # what a temperature sensor can physically report
    "temp_max_c": 60,
    "zero_f_in_c": (0 - 32) * 5 / 9,  # a dropout, after converting: -17.777...
}

# Steps 2-7 as one query. Each WITH block is one step.
quality_query = """
CREATE TEMP TABLE quality AS
WITH
step2 AS (                -- 2. convert temperatures to degC
  SELECT *,
         (discharge_air_temp_f - 32) * 5 / 9 AS dat_c,
         (dat_reset_f - 32) * 5 / 9          AS dat_setpoint_c
  FROM ahu_1
),
step3 AS (                -- 3-5, 7. flags per row; 6a. a new flat streak starts where value changes
  SELECT timestamp_utc, supply_fan_status, dat_c, dat_setpoint_c,
         discharge_air_temp_f = 0 OR mixed_air_temp_f = 0 OR return_air_temp_f = 0 AS dropout,
         supply_fan_status = 1 AND dat_reset_f = 0                               AS setpoint_zero,
         dat_c NOT BETWEEN :temp_min_c AND :temp_max_c                           AS out_of_range,
         discharge_air_temp_f IS NOT LAG(discharge_air_temp_f) OVER w            AS new_flat,
         unixepoch(timestamp_utc) - LAG(unixepoch(timestamp_utc)) OVER w         AS step_s
  FROM step2
  WINDOW w AS (ORDER BY timestamp_utc)
),
step6b AS (               -- 6b. running total of the marks numbers each flat streak
  SELECT *, SUM(new_flat) OVER (ORDER BY timestamp_utc) AS flat_id
  FROM step3
),
step6c AS (               -- 6c. rows in each streak, and how many of them had the fan on
  SELECT *,
         COUNT(*) OVER (PARTITION BY flat_id)               AS streak_rows,
         SUM(supply_fan_status) OVER (PARTITION BY flat_id) AS streak_fan_rows
  FROM step6b
)
SELECT *,
       streak_rows >= :flat_rows AND streak_fan_rows = streak_rows AS flatline,
       substr(timestamp_utc, 1, 7) AS month
FROM step6c
"""
conn.execute(quality_query, settings)

# 8. The rule, once for "ungated" (every row) and once for "gated" (skip bad-data rows)
rule_query = """
CREATE TEMP TABLE rule AS
WITH
raw AS (                  -- 8a. raw fault: fan on and |discharge - setpoint| > 2.78 degC
  SELECT 'ungated' AS variant, timestamp_utc, month,
         supply_fan_status = 1 AND ABS(dat_c - dat_setpoint_c) > :tolerance_c AS raw
  FROM quality
  UNION ALL
  SELECT 'gated', timestamp_utc, month,
         supply_fan_status = 1 AND dropout = 0 AND setpoint_zero = 0
           AND ABS(dat_c - dat_setpoint_c) > :tolerance_c
  FROM quality
),
marks AS (                -- 8b. a new streak starts wherever the flag changes (per variant)
  SELECT *,
         raw IS NOT LAG(raw) OVER (PARTITION BY variant ORDER BY timestamp_utc) AS new_streak
  FROM raw
),
ids AS (                  -- 8c. number the streaks
  SELECT *,
         SUM(new_streak) OVER (PARTITION BY variant ORDER BY timestamp_utc) AS streak_id
  FROM marks
)
SELECT variant, month,    -- 8d. confirm: the flag has held for 6 rows
       raw = 1 AND ROW_NUMBER() OVER (PARTITION BY variant, streak_id ORDER BY timestamp_utc)
                   >= :confirm_rows AS fault
FROM ids
"""
conn.execute(rule_query, settings)

# Totals of the checks
checks_query = """
SELECT SUM(dropout),
       SUM(setpoint_zero),
       SUM(out_of_range),
       SUM(flatline),
       COUNT(DISTINCT CASE WHEN flatline = 1 THEN flat_id END),
       SUM(step_s <> 300),
       MAX(step_s),
       SUM(dat_c = -17.78),
       SUM(ABS(dat_c - :zero_f_in_c) < 0.01)
FROM quality
"""
row = conn.execute(checks_query, settings).fetchone()
dropouts, setpoint_zero, out_of_range, flatline_rows, flat_episodes = row[:5]
step_gaps, max_step_s, exact_matches, tolerance_matches = row[5:]

# 9. Fault hours: rows x 5 / 60, per month and in total
monthly_query = """
SELECT month,
       SUM(CASE WHEN variant = 'ungated' THEN fault END) * 5 / 60.0 AS ungated_fault_h,
       SUM(CASE WHEN variant = 'gated' THEN fault END) * 5 / 60.0   AS gated_fault_h
FROM rule
GROUP BY month
ORDER BY month
"""
monthly = pd.read_sql_query(monthly_query, conn)
ungated_h = monthly["ungated_fault_h"].sum()
gated_h = monthly["gated_fault_h"].sum()

print("AHU_1 data-quality checks")
print("  dropout rows (a temperature reads 0 F):", dropouts)
print("  setpoint reads 0 while the fan runs:   ", setpoint_zero)
print("  discharge temp out of range:           ", out_of_range)
print("  flatline rows (1 h+ the same value):   ", flatline_rows)
print("  flatline episodes:                     ", flat_episodes)
print("  time steps that are not 300 s:         ", step_gaps)
print("  longest time step (s):                 ", max_step_s)
print("  dat_c == -17.78 matches:               ", exact_matches)
print("  dat_c within 0.01 of -17.78 matches:   ", tolerance_matches)
print("Challenge: discharge air temp fault hours")
print(monthly.round(2).to_string(index=False))
print("  total, trusting every row (h):", round(ungated_h, 2))
print("  total, quality gate on (h):   ", round(gated_h, 2))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "dropout_rows": dropouts,
    "setpoint_zero_rows": setpoint_zero,
    "out_of_range_rows": out_of_range,
    "flatline_rows": flatline_rows,
    "flat_episodes": flat_episodes,
    "step_gaps": step_gaps,
    "max_step_s": max_step_s,
    "exact_matches": exact_matches,
    "tolerance_matches": tolerance_matches,
    "ungated_fault_h": ungated_h,
    "gated_fault_h": gated_h,
    "monthly_fault_hours": monthly,
}
