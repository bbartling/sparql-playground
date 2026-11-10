# Day 1 (SQL): the same AHU_1 data, loaded as the SQLite table `ahu_1`.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day01_sql.py

import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

# 1. Count the rows
rows = conn.execute("SELECT COUNT(*) FROM ahu_1").fetchone()[0]
print("Rows:", rows)

# 2. Count the columns (SQLite lists a table's columns in pragma_table_info)
columns = conn.execute("SELECT COUNT(*) FROM pragma_table_info('ahu_1')").fetchone()[0]
print("Columns:", columns)

# 3. The first five column names
names_sql = "SELECT name FROM pragma_table_info('ahu_1') ORDER BY cid LIMIT 5"
column_names = [row[0] for row in conn.execute(names_sql).fetchall()]
print("First column names:", column_names)

# 4. The first five rows of a few columns
first_rows_sql = """
SELECT timestamp_utc, outside_air_temp_f, da_p_inwc, da_p_setpoint_inwc
FROM ahu_1
ORDER BY timestamp_utc
LIMIT 5
"""
first_rows = pd.read_sql_query(first_rows_sql, conn)
print(first_rows.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"rows": rows, "columns": columns, "first_rows": first_rows}
