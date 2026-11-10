# Day 9 (SQL): hourly and daily averages of AHU_1's outside air temperature.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day09_sql.py

import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

# 1-4. The bucket is the hour (or day) as text; GROUP BY it and average
hourly_query = """
SELECT strftime('%Y-%m-%d %H', timestamp_utc) AS hour,      -- the hour this row is in
       COUNT(*) AS rows,
       AVG((outside_air_temp_f - 32) * 5 / 9.0) AS mean_oa_c
FROM ahu_1
GROUP BY hour
ORDER BY hour
"""
daily_query = """
SELECT strftime('%Y-%m-%d', timestamp_utc) AS day,          -- the day this row is in
       COUNT(*) AS rows,
       AVG((outside_air_temp_f - 32) * 5 / 9.0) AS mean_oa_c
FROM ahu_1
GROUP BY day
ORDER BY day
"""
hourly = pd.read_sql_query(hourly_query, conn)
daily = pd.read_sql_query(daily_query, conn)

# 5. The hottest day
hottest = daily.sort_values("mean_oa_c").iloc[-1]

print("Hourly rows:", len(hourly))
print("Daily rows: ", len(daily))
print("First hour:", hourly["hour"][0], "has only", hourly["rows"][0], "rows (a partial hour)")
print("Hottest day:", hottest["day"], "at", round(hottest["mean_oa_c"], 1), "C")

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"hourly": hourly, "daily": daily}
