# Day 13 (SQL): streaks. The longest fan run, and "true for 6 rows in a row".
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day13_sql.py

import sqlite3

conn = sqlite3.connect("var/lessons.sqlite")

settings = {
    "full_speed_pct": 95,  # "at or near full speed"
    "confirm_rows": 6,  # 6 rows x 5 min = 30 minutes
}

# 2-3. Fan runs. Number the streaks of the fan status, then keep the ones where the fan is on.
runs_query = """
CREATE TEMP TABLE runs AS
WITH
marks AS (                -- 2a. a new streak starts wherever the value changes
  SELECT timestamp_utc, supply_fan_status,
         supply_fan_status IS NOT LAG(supply_fan_status) OVER (ORDER BY timestamp_utc)
           AS new_streak
  FROM ahu_1
),
ids AS (                  -- 2b. a running total of the marks numbers each streak
  SELECT *, SUM(new_streak) OVER (ORDER BY timestamp_utc) AS streak_id
  FROM marks
)
SELECT streak_id,         -- 3. each streak with the fan on is one run
       MIN(timestamp_utc) AS start_utc,
       COUNT(*) AS n_rows,
       COUNT(*) * 5 / 60.0 AS hours
FROM ids
WHERE supply_fan_status = 1
GROUP BY streak_id
"""
conn.execute(runs_query)

runs, avg_run_hours = conn.execute("SELECT COUNT(*), AVG(hours) FROM runs").fetchone()

# 4. The longest run (ties: the earliest)
longest_rows, longest_hours, longest_start = conn.execute("""
    SELECT n_rows, hours, start_utc
    FROM runs
    ORDER BY n_rows DESC, start_utc
    LIMIT 1
""").fetchone()

# 5-6. "Full speed for 6 rows in a row", by streak and by a rolling sum of the last 6 flags
confirm_query = """
CREATE TEMP TABLE confirm AS
WITH
raw AS (                  -- 5a. raw flag: fan on AND at full speed
  SELECT timestamp_utc,
         supply_fan_status = 1 AND supply_fan_speed_pct >= :full_speed_pct AS raw
  FROM ahu_1
),
marks AS (                -- 5b. streak starts, and the rolling sum of the last 6 flags (route 2)
  SELECT *,
         raw IS NOT LAG(raw) OVER (ORDER BY timestamp_utc) AS new_streak,
         SUM(raw) OVER (ORDER BY timestamp_utc
                        ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS last_6_sum
  FROM raw
),
ids AS (                  -- 5c. number the streaks
  SELECT *, SUM(new_streak) OVER (ORDER BY timestamp_utc) AS streak_id
  FROM marks
)
SELECT raw,
       streak_id,
       raw = 1 AND ROW_NUMBER() OVER (PARTITION BY streak_id ORDER BY timestamp_utc)
                   >= :confirm_rows AS confirmed_streak,
       last_6_sum = :confirm_rows AS confirmed_window
FROM ids
"""
conn.execute(confirm_query, settings)

raw_rows, confirmed_streak, confirmed_window, episodes = conn.execute("""
    SELECT SUM(raw),
           SUM(confirmed_streak),
           SUM(confirmed_window),
           COUNT(DISTINCT CASE WHEN confirmed_streak = 1 THEN streak_id END)
    FROM confirm
""").fetchone()

print("AHU_1 fan runs (status = 1)")
print("  runs:", runs)
print("  average run (hours):", round(avg_run_hours, 2))
print("  longest run (rows):", longest_rows)
print("  longest run (hours):", round(longest_hours, 2))
print("  longest run started:", longest_start)
print("Full speed (>= 95 %) for 6 rows in a row")
print("  raw rows:", raw_rows)
print("  confirmed rows (streak route):", confirmed_streak)
print("  confirmed rows (rolling route):", confirmed_window)
print("  episodes:", episodes)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "runs": runs,
    "avg_run_hours": avg_run_hours,
    "longest_rows": longest_rows,
    "longest_hours": longest_hours,
    "longest_start": longest_start,
    "raw_rows": raw_rows,
    "confirmed_rows_streak": confirmed_streak,
    "confirmed_rows_window": confirmed_window,
    "episodes": episodes,
}
