# Day 7 (SQL): stack the two AHUs, then join them on time to compare their outside air sensors.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day07_sql.py

import sqlite3

conn = sqlite3.connect("var/lessons.sqlite")

# 1-2. Stack: UNION ALL puts the rows of AHU_2 below the rows of AHU_1
stacked_rows = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT 'AHU_1' AS equipment_id, timestamp_utc, outside_air_temp_f FROM ahu_1
        UNION ALL
        SELECT 'AHU_2', timestamp_utc, outside_air_temp_f FROM ahu_2
    )
""").fetchone()[0]

# 3-4. Join on the timestamp, then measure the gap (degF * 5/9 = kelvin)
joined_rows, mean_diff_k, rows_over_2k, rows_over_20k = conn.execute("""
    WITH both AS (
        SELECT ABS(a.outside_air_temp_f - b.outside_air_temp_f) * 5 / 9.0 AS diff_k
        FROM ahu_1 AS a
        JOIN ahu_2 AS b ON b.timestamp_utc = a.timestamp_utc
    )
    SELECT COUNT(*), AVG(diff_k), SUM(diff_k > 2), SUM(diff_k > 20)
    FROM both
""").fetchone()

print("Rows in the stacked table:", stacked_rows)
print("Rows in the joined table: ", joined_rows)
print("Average gap between the sensors (K):", round(mean_diff_k, 2))
print("Rows more than 2 K apart: ", rows_over_2k)
print("Rows more than 20 K apart:", rows_over_20k)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "stacked_rows": stacked_rows,
    "joined_rows": joined_rows,
    "mean_gap_k": mean_diff_k,
    "rows_over_2k": rows_over_2k,
    "rows_over_20k": rows_over_20k,
}
