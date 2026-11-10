# Day 14 (SQL): fault rule FC1, "duct static pressure too low while the fan runs".
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day14_sql.py

import sqlite3

conn = sqlite3.connect("var/lessons.sqlite")

# Rule settings
settings = {
    "pa_per_inh2o": 249.08891,  # 1 inch of water = 249.09 pascals
    "tolerance_pa": 25,  # how far below setpoint counts as "too low"
    "confirm_rows": 2,  # the fault must last 2 rows in a row (2 x 5 min = 10 minutes)
}

# Steps 1-4 as one query. Each WITH block is one step; read them top to bottom.
fc1_query = """
CREATE TEMP TABLE fc1 AS
WITH
step2 AS (                -- 1-2. read AHU_1 and convert the pressures to pascals
  SELECT timestamp_utc,
         supply_fan_status,
         da_p_inwc * :pa_per_inh2o          AS static_pa,
         da_p_setpoint_inwc * :pa_per_inh2o AS setpoint_pa
  FROM ahu_1
),
step3 AS (                -- 3. raw fault: fan on AND static more than 25 Pa below setpoint
  SELECT timestamp_utc,
         supply_fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa AS raw_fault
  FROM step2
),
step4a AS (               -- 4a. mark rows where the value changes (a new streak starts)
  SELECT *,
         raw_fault IS NOT LAG(raw_fault) OVER (ORDER BY timestamp_utc) AS new_streak
  FROM step3
),
step4b AS (               -- 4b. a running total of those marks numbers each streak
  SELECT *,
         SUM(new_streak) OVER (ORDER BY timestamp_utc) AS streak_id
  FROM step4a
)
SELECT timestamp_utc,     -- 4c. count rows inside each streak, keep the long-enough faults
       raw_fault,
       streak_id,
       raw_fault = 1
         AND ROW_NUMBER() OVER (PARTITION BY streak_id ORDER BY timestamp_utc) >= :confirm_rows
         AS fault
FROM step4b
"""
conn.execute(fc1_query, settings)

# 5. Totals: each row is 5 minutes, so rows x 5 / 60 = hours
raw_hours, fault_hours, episodes = conn.execute("""
    SELECT SUM(raw_fault) * 5 / 60.0,
           SUM(fault) * 5 / 60.0,
           COUNT(DISTINCT CASE WHEN fault = 1 THEN streak_id END)
    FROM fc1
""").fetchone()

# 6. Open-FDD's results for the same data, and how many of its FC1 episodes we also found
openfdd_episodes, openfdd_hours = conn.execute("""
    SELECT COUNT(*), SUM(duration_min) / 60
    FROM fdd_events
    WHERE rule_name = 'fc1' AND hvac_system = 'bld_50_AHU_1'
""").fetchone()

found = conn.execute("""
    SELECT COUNT(*)
    FROM fdd_events AS e
    WHERE e.rule_name = 'fc1' AND e.hvac_system = 'bld_50_AHU_1'
      AND EXISTS (SELECT 1 FROM fc1
                  WHERE fc1.fault = 1
                    AND fc1.timestamp_utc BETWEEN e.start_time_utc AND e.end_time_utc)
""").fetchone()[0]

print("AHU_1, FC1 (duct static too low)")
print("  raw fault hours:      ", round(raw_hours, 2))
print("  confirmed fault hours:", round(fault_hours, 2))
print("  confirmed episodes:   ", episodes)
print("Open-FDD, FC1 on AHU_1")
print("  episodes:", openfdd_episodes)
print("  hours:   ", round(openfdd_hours, 1))
print("Open-FDD episodes that contain one of our faults:", found, "of", openfdd_episodes)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "raw_hours": raw_hours,
    "fault_hours": fault_hours,
    "episodes": episodes,
    "openfdd_episodes": openfdd_episodes,
    "overlap": found,
}
