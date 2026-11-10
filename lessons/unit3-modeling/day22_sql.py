# Day 22 (SQL): find FC1's inputs for AHU_1 by role, in a flat point table.
# Run from the repo root:
#     uv run python lessons/unit3-modeling/day22_sql.py
#
# model/points/BUILDING_50__AHU_1.csv is the point list the RDF model was built from, one row
# per point. It goes into a small in-memory SQLite table, and we ask the same question of it:
# which points play FC1's roles?

import sqlite3

import pandas as pd

conn = sqlite3.connect(":memory:")  # nothing to set up: the table is built from the CSV below

# 1. Load the flat point list into a table called `point` (one row per point)
points = pd.read_csv("model/points/BUILDING_50__AHU_1.csv")
points["equipment_id"] = "AHU_1"  # the file is AHU_1's, so say so in a column
points.to_sql("point", conn, index=False)

# 2. What does one point look like? One row. The table has columns where the graph has tags.
#    (There are no markers here: the CSV never had them. The graph adds them.)
one_point = pd.read_sql_query("SELECT * FROM point WHERE point_id = 'AHU_1_DA_P'", conn)

# 3. FC1's three inputs, by role: a WHERE on the role column
fc1_sql = """
SELECT equipment_id, openfdd_role AS role, point_id, timeseries_id
FROM point
WHERE openfdd_role IN ('fan-status', 'duct-static-pressure', 'duct-static-pressure-sp')
ORDER BY role
"""
fc1_inputs = pd.read_sql_query(fc1_sql, conn)

# 4. How many AHU_1 points carry a fault-rule role at all?
roles_count = conn.execute("SELECT COUNT(openfdd_role) FROM point").fetchone()[0]

print("The point table has", len(points), "rows (one per point).")
print("\nOne point, as a row:")
print(one_point.T.to_string(header=False))
print("\nFC1's inputs on AHU_1, found by role:")
print(fc1_inputs.to_string(index=False))
print("\nAHU_1 points with a fault-rule role:", roles_count)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fc1_inputs": fc1_inputs, "roles_count": roles_count}
