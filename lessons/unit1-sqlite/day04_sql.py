# Day 4 (SQL): average, min and max of a column, and fan run hours.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day04_sql.py

import sqlite3

conn = sqlite3.connect("var/lessons.sqlite")

# 1. The table is ahu_1

# 2. Average, minimum and maximum outside air temperature
stats_sql = """
SELECT AVG(outside_air_temp_f), MIN(outside_air_temp_f), MAX(outside_air_temp_f)
FROM ahu_1
"""
average_f, min_f, max_f = conn.execute(stats_sql).fetchone()
print("Outside air temperature (F): average", round(average_f, 2), "min", min_f, "max", max_f)

# 3. Run hours: fan status is 1 when running, 0 when off, one reading every 5 minutes
# (60.0, not 60: SQLite drops the decimals of integer / integer)
run_hours = conn.execute("SELECT SUM(supply_fan_status) * 5 / 60.0 FROM ahu_1").fetchone()[0]
print("Supply fan run hours:", round(run_hours, 1))

# 4. The average of a 0/1 column is the fraction of time it was 1
fraction_running = conn.execute("SELECT AVG(supply_fan_status) FROM ahu_1").fetchone()[0]
print("Fraction of time the fan ran:", round(fraction_running, 3))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "average_f": average_f,
    "min_f": min_f,
    "max_f": max_f,
    "run_hours": run_hours,
    "fraction_running": fraction_running,
}
