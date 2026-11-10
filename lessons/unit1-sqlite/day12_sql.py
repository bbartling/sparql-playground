# Day 12 (SQL): look at neighbouring rows: LAG/LEAD, a rolling mean, and fan starts and stops.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day12_sql.py

import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

settings = {"pa_per_inh2o": 249.08891}  # 1 inch of water = 249.09 pascals

# Steps 2-5 as one query. Each WITH block is one step.
windows_query = """
CREATE TEMP TABLE windows AS
WITH
step2 AS (                -- 2. convert duct static to pascals
  SELECT timestamp_utc, supply_fan_status,
         da_p_inwc * :pa_per_inh2o AS static_pa
  FROM ahu_1
),
step3 AS (                -- 3-5. previous / 3-rows-ahead (LAG / LEAD), 1-hour mean, previous fan
  SELECT timestamp_utc, supply_fan_status, static_pa,
         LAG(static_pa)     OVER (ORDER BY timestamp_utc) AS static_prev_pa,
         LEAD(static_pa, 3) OVER (ORDER BY timestamp_utc) AS static_ahead_pa,
         AVG(static_pa) OVER (ORDER BY timestamp_utc
                              ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS static_1h_mean_pa,
         LAG(supply_fan_status) OVER (ORDER BY timestamp_utc) AS fan_prev
  FROM step2
)
SELECT *,
       supply_fan_status = 1 AND fan_prev = 0 AS fan_start,   -- on now, off in the previous row
       supply_fan_status = 0 AND fan_prev = 1 AS fan_stop     -- off now, on in the previous row
FROM step3
"""
conn.execute(windows_query, settings)

# 6. Totals, and static 15 minutes after each start
fan_starts, fan_stops, max_mean, first_start, avg_after_start = conn.execute("""
    SELECT SUM(fan_start),
           SUM(fan_stop),
           MAX(static_1h_mean_pa),
           MIN(CASE WHEN fan_start = 1 THEN timestamp_utc END),
           AVG(CASE WHEN fan_start = 1 THEN static_ahead_pa END)
    FROM windows
""").fetchone()

events = pd.read_sql_query(
    """
    SELECT timestamp_utc, fan_start, fan_stop
    FROM windows
    WHERE fan_start = 1 OR fan_stop = 1
    ORDER BY timestamp_utc
""",
    conn,
)

print("AHU_1 fan cycling (duct static in Pa)")
print("  fan starts:", fan_starts)
print("  fan stops: ", fan_stops)
print("  highest 1-hour mean static (Pa):", round(max_mean, 1))
print("  first fan start:", first_start)
print("  average static 15 min after a start (Pa):", round(avg_after_start, 2))
print("First 3 fan events (start=1 or stop=1):")
print(events.head(3).to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "fan_starts": fan_starts,
    "fan_stops": fan_stops,
    "max_static_1h_mean_pa": max_mean,
    "first_start": first_start,
    "avg_static_15min_after_start_pa": avg_after_start,
    "fan_events": events,
}
