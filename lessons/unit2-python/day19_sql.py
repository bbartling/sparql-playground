# Day 19 (SQL): the as-of join. Give every AHU row the latest weather reading, if it is recent.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day19_sql.py

import sqlite3
import time

conn = sqlite3.connect("var/lessons.sqlite")

settings = {
    "rows": 100_000,  # AHU_1's first 100,000 rows (rowid 1 to 100,000 in the table)
    "max_age_seconds": 2 * 3600,  # weather older than 2 hours is "stale": unknown, not used
    "diff_c": 3,  # the sensor and the weather may differ by up to 3 C
    "confirm_rows": 6,  # 6 rows x 5 min = 30 minutes
}

# 1-2. The as-of join. For each AHU row, a small query inside the big one finds the latest
#      weather time at or before it, no older than the limit. setup_db.py made an index on
#      synthetic_weather(ts), so each lookup is a quick search, not a scan.
join_sql = """
CREATE TEMP TABLE joined AS
SELECT h.ts, h.fan_status, h.oat_c,
       (SELECT w.ts FROM synthetic_weather AS w
        WHERE w.ts <= h.ts AND w.ts >= h.ts - :max_age_seconds
        ORDER BY w.ts DESC
        LIMIT 1) AS weather_ts
FROM synthetic AS h
WHERE h.rowid <= :rows
"""
start = time.perf_counter()
conn.execute(join_sql, settings)
index_seconds = time.perf_counter() - start

# Now look up the temperature at that weather time (an ordinary join on equal times)
conn.execute("""
CREATE TEMP TABLE with_weather AS
SELECT j.*, w.temp_c AS weather_c
FROM joined AS j
LEFT JOIN synthetic_weather AS w ON w.ts = j.weather_ts
""")
rows_without_weather, average_weather_c = conn.execute(
    "SELECT SUM(weather_c IS NULL), AVG(weather_c) FROM with_weather"
).fetchone()

# 3-4. The same subquery on a copy of the weather table with no index, first 200 rows only.
#      Without the index SQLite has to read the whole weather table for every AHU row.
conn.execute("CREATE TEMP TABLE weather_copy AS SELECT * FROM synthetic_weather")
slow_sql = """
SELECT h.ts,
       (SELECT w.ts FROM weather_copy AS w
        WHERE w.ts <= h.ts AND w.ts >= h.ts - :max_age_seconds
        ORDER BY w.ts DESC
        LIMIT 1) AS weather_ts
FROM synthetic AS h
WHERE h.rowid <= 200
"""
start = time.perf_counter()
conn.execute(slow_sql, settings).fetchall()
no_index_seconds = time.perf_counter() - start

# 5. The sensor-versus-weather rule: fan on and more than 3 C apart, for 6 rows in a row.
#    No weather (NULL) means no fault. The streak steps are Day 14's.
rule_sql = """
WITH
step1 AS (
  SELECT ts,
         COALESCE(fan_status = 1 AND ABS(oat_c - weather_c) > :diff_c, 0) AS raw_fault
  FROM with_weather
),
step2 AS (
  SELECT *, raw_fault IS NOT LAG(raw_fault) OVER (ORDER BY ts) AS new_streak
  FROM step1
),
step3 AS (
  SELECT *, SUM(new_streak) OVER (ORDER BY ts) AS streak_id
  FROM step2
),
step4 AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY streak_id ORDER BY ts) AS row_in_streak
  FROM step3
)
SELECT SUM(raw_fault),
       SUM(raw_fault = 1 AND row_in_streak >= :confirm_rows)
FROM step4
"""
raw_rows, fault_rows = conn.execute(rule_sql, settings).fetchone()
fault_hours = fault_rows * 5 / 60

ahu_rows = conn.execute("SELECT COUNT(*) FROM joined").fetchone()[0]
weather_rows = conn.execute("SELECT COUNT(*) FROM synthetic_weather").fetchone()[0]
print("AHU rows:", ahu_rows, "| weather rows:", weather_rows)
print("Rows with no usable weather:", rows_without_weather)
print("Average weather temperature on the matched rows (C):", round(average_weather_c, 3))
print("\nSensor vs weather rule (fan on, more than 3 C apart for 30 minutes):")
print("  raw rows:", raw_rows, "| confirmed rows:", fault_rows, "| hours:", round(fault_hours, 2))
print("\nMicroseconds per AHU row (times vary by machine):")
print("  no index:  ", round(no_index_seconds / 200 * 1_000_000, 2))
print("  with index:", round(index_seconds / ahu_rows * 1_000_000, 2))

# How SQLite runs the subquery, with and without the index
for table in ["synthetic_weather", "weather_copy"]:
    plan_sql = (
        "EXPLAIN QUERY PLAN SELECT ts FROM " + table + " WHERE ts <= 0 AND ts >= -7200"
        " ORDER BY ts DESC LIMIT 1"
    )
    plan = [row[3] for row in conn.execute(plan_sql)]
    print("Plan on", table + ":", " | ".join(plan))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "rows_without_weather": rows_without_weather,
    "average_weather_c": average_weather_c,
    "raw_rows": raw_rows,
    "fault_rows": fault_rows,
    "fault_hours": fault_hours,
}
