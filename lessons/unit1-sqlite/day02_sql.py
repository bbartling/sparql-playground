# Day 2 (SQL): pick columns and filter rows.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day02_sql.py

import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

limit_inwc = 1.5  # "high" duct static pressure, in inches of water

# 1. The table is ahu_1 (the CSV, unchanged)

# 2. Pick two columns and keep the first three rows
first_three_sql = """
SELECT timestamp_utc, outside_air_temp_f
FROM ahu_1
ORDER BY timestamp_utc
LIMIT 3
"""
first_three = pd.read_sql_query(first_three_sql, conn)
print(first_three.to_string(index=False))

# 3. Sort by temperature; the first row is the coldest reading
coldest_sql = """
SELECT timestamp_utc, outside_air_temp_f
FROM ahu_1
ORDER BY outside_air_temp_f, timestamp_utc
LIMIT 1
"""
coldest = pd.read_sql_query(coldest_sql, conn)
print("Coldest reading:")
print(coldest.to_string(index=False))

# 4. Filter rows (WHERE): how many readings had duct static above the limit?
high_static_sql = "SELECT COUNT(*) FROM ahu_1 WHERE da_p_inwc > :limit"
high_static = conn.execute(high_static_sql, {"limit": limit_inwc}).fetchone()[0]
print("Readings with static above", limit_inwc, "inH2O:", high_static)

# 5. Two conditions: the fan is on AND static is below 0.5
fan_on_low_sql = "SELECT COUNT(*) FROM ahu_1 WHERE supply_fan_status = 1 AND da_p_inwc < 0.5"
fan_on_low = conn.execute(fan_on_low_sql).fetchone()[0]
print("Fan on but static below 0.5 inH2O:", fan_on_low)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "first_three": first_three,
    "coldest": coldest,
    "high_static": high_static,
    "fan_on_low": fan_on_low,
}
