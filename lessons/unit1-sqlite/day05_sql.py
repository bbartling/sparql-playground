# Day 5 (SQL): group by month and by day.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day05_sql.py

import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

# 1. The table is ahu_1

# 2-3. The Week 1 challenge, one row per month: average temperature, fan run hours, high static
# (strftime('%Y-%m', ...) turns a timestamp into a month label like "2026-03")
monthly_sql = """
SELECT strftime('%Y-%m', timestamp_utc)   AS month,
       AVG(outside_air_temp_f)            AS avg_oat_f,
       SUM(supply_fan_status) * 5 / 60.0  AS fan_run_hours,
       SUM(da_p_inwc > 1.5)               AS static_above_1_5
FROM ahu_1
GROUP BY month
ORDER BY month
"""
monthly = pd.read_sql_query(monthly_sql, conn)
print(monthly.round(1).to_string(index=False))

# 4. The hottest day on average
hottest_sql = """
SELECT date(timestamp_utc) AS day, AVG(outside_air_temp_f) AS avg_f
FROM ahu_1
GROUP BY day
ORDER BY avg_f DESC
LIMIT 1
"""
hottest_day, hottest_avg = conn.execute(hottest_sql).fetchone()
print("Hottest day:", hottest_day, "average (F):", round(hottest_avg, 2))

# 5. Days with fewer than 288 readings (24 hours x 12 per hour)
short_days_sql = """
SELECT date(timestamp_utc) AS day, COUNT(*) AS n
FROM ahu_1
GROUP BY day
HAVING COUNT(*) < 288    -- HAVING filters groups, after they are counted
"""
short_days = pd.read_sql_query(short_days_sql, conn)
print(short_days.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "monthly": monthly,
    "hottest_day": hottest_day,
    "hottest_avg": hottest_avg,
    "short_days": short_days,
}
