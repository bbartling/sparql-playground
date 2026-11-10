# Day 18 (SQL): FC1 on data with holes: sample-and-hold, a gap limit, and coverage.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day18_sql.py

import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

settings = {
    "start_ts": 1_773_619_200,  # the synthetic data's first timestamp (epoch seconds)
    "tolerance_pa": 25,  # how far below setpoint counts as "too low"
    "max_gap_seconds": 3600,  # a silence longer than 1 hour is "unknown", not "still faulty"
    "confirm_seconds": 600,  # a fault must last 10 minutes (Day 14's two 5-minute rows)
}

# 1-2. The first 4,000 rows of each AHU, with the same holes as the pandas script:
#      every 37th row dropped, and 100 rows of AHU_1 in a row (an outage of about 8 hours)
gappy_sql = """
CREATE TEMP TABLE gappy AS
SELECT equipment_id, ts, fan_status, static_pa, setpoint_pa
FROM synthetic
WHERE (ts - :start_ts) / 300 < 4000
  AND (ts - :start_ts) / 300 % 37 != 5
  AND NOT (equipment_id = 'AHU_1' AND (ts - :start_ts) / 300 BETWEEN 400 AND 499)
"""
conn.execute(gappy_sql, settings)

# 3-6. One query, one WITH block per step. PARTITION BY equipment_id keeps the AHUs apart.
rows_sql = """
CREATE TEMP TABLE fc1 AS
WITH
step3 AS (                -- 3. raw fault, the same as Day 14
  SELECT equipment_id, ts,
         fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa AS raw_fault
  FROM gappy
),
step4a AS (               -- 4a. seconds until the next reading (LEAD looks one row ahead)
  SELECT *,
         LEAD(ts) OVER (PARTITION BY equipment_id ORDER BY ts) - ts AS seconds_to_next
  FROM step3
),
step4b AS (               -- 4b. sample-and-hold; a gap longer than the limit holds 0 seconds
  SELECT *,
         COALESCE(seconds_to_next > :max_gap_seconds, 0) AS gap_after,
         CASE WHEN seconds_to_next > :max_gap_seconds THEN 0
              ELSE COALESCE(seconds_to_next, 0) END AS held_seconds
  FROM step4a
),
step5a AS (               -- 5a. a new streak starts when raw_fault changes, or after a long gap
  SELECT *,
         raw_fault IS NOT LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
           OR LAG(gap_after) OVER (PARTITION BY equipment_id ORDER BY ts) = 1 AS new_streak
  FROM step4b
),
step5b AS (               -- 5b. a running total of those marks numbers each streak
  SELECT *,
         SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id
  FROM step5a
),
step6 AS (                -- 6. elapsed time inside each streak
  SELECT *,
         SUM(held_seconds) OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_seconds
  FROM step5b
)
SELECT *, raw_fault = 1 AND streak_seconds >= :confirm_seconds AS fault
FROM step6
"""
conn.execute(rows_sql, settings)

# 7. Per AHU: fault hours, covered hours (time we can vouch for) and coverage
summary_sql = """
SELECT equipment_id,
       COUNT(*) AS rows,
       SUM(gap_after) AS long_gaps,
       SUM(CASE WHEN fault = 1 THEN held_seconds ELSE 0 END) / 3600.0 AS fault_hours,
       SUM(held_seconds) / 3600.0 AS covered_hours,
       (MAX(ts) - MIN(ts)) / 3600.0 AS window_hours,
       SUM(held_seconds) * 1.0 / (MAX(ts) - MIN(ts)) AS coverage
FROM fc1
GROUP BY equipment_id
"""
summary = pd.read_sql_query(summary_sql, conn)

# 8. The wrong way, for comparison: Day 14's rule (count rows x 5 minutes, ignore the gaps)
naive_sql = """
WITH
marks AS (
  SELECT equipment_id, ts, raw_fault,
         raw_fault IS NOT LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts) AS new_streak
  FROM fc1
),
streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id
  FROM marks
),
numbered AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS row_in_streak
  FROM streaks
)
SELECT equipment_id, SUM(raw_fault = 1 AND row_in_streak >= 2) * 5 / 60.0 AS naive_fault_hours
FROM numbered
GROUP BY equipment_id
"""
naive = pd.read_sql_query(naive_sql, conn)

rows_left = conn.execute("SELECT COUNT(*) FROM gappy").fetchone()[0]
print("Rows left after the holes:", rows_left, "of 8000")
print("\nGap-aware FC1 per AHU:")
print(summary.round(3).to_string(index=False))
print("\nRow counting (Day 14) on the same rows:")
print(naive.round(2).to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"summary": summary, "naive_fault_hours": naive}
