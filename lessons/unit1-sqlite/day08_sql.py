# Day 8 (SQL): conditional counts with CASE. Run hours, unoccupied runtime, percent occupied.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day08_sql.py

import sqlite3

conn = sqlite3.connect("var/lessons.sqlite")

settings = {"pa_per_inh2o": 249.08891}  # 1 inch of water = 249.09 pascals

# 1-4. CASE gives 1 or 0 for each row; SUM adds them up, so SUM(CASE ...) counts the rows
query = """
SELECT SUM(CASE WHEN supply_fan_status = 1 THEN 1 ELSE 0 END),                -- fan on
       SUM(CASE WHEN supply_fan_status = 1 AND occ_c <> 1 THEN 1 ELSE 0 END), -- fan on, unoccupied
       SUM(CASE WHEN occ_c = 1 THEN 1 ELSE 0 END),                            -- occupied
       COUNT(*),                                                              -- all rows
       -- AVG skips NULL, and a CASE with no ELSE gives NULL: only fan-on rows get averaged
       AVG(CASE WHEN supply_fan_status = 1 THEN da_p_inwc * :pa_per_inh2o END)
FROM ahu_1
"""
fan_on_rows, unoccupied_rows, occupied_rows, all_rows, static_running_pa = conn.execute(
    query, settings
).fetchone()

# Each row is 5 minutes, so rows x 5 / 60 = hours
run_hours = fan_on_rows * 5 / 60
unoccupied_run_hours = unoccupied_rows * 5 / 60
percent_occupied = 100.0 * occupied_rows / all_rows
percent_run_unoccupied = 100 * unoccupied_run_hours / run_hours

print("Run hours:", round(run_hours, 2))
print("Run hours while unoccupied:", round(unoccupied_run_hours, 2))
print("Percent of rows occupied:", round(percent_occupied, 2))
print("Percent of run time unoccupied:", round(percent_run_unoccupied, 2))
print("Average static while the fan runs (Pa):", round(static_running_pa, 1))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "run_hours": run_hours,
    "unoccupied_run_hours": unoccupied_run_hours,
    "percent_occupied": percent_occupied,
    "percent_run_unoccupied": percent_run_unoccupied,
    "static_running_pa": static_running_pa,
}
