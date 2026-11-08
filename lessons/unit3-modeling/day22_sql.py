"""Day 22, SQL: find FC1's inputs by role, in a flat point table (a shadow of the RDF graph).

    uv run python lessons/unit3-modeling/day22_sql.py

model/points/*.csv is the point list the RDF model was built from, one row per point. It goes into
a TEMP table, and the same question is asked of it: which points play
FC1's roles? SQLite does the work; pandas only collects the rows for printing. Compare the
printout with day22_pandas.py: the same (equipment, role, point) rows come back."""

import csv
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POINT_CSVS = sorted((ROOT / "model" / "points").glob("*.csv"))
conn = sqlite3.connect(":memory:")  # nothing to set up: the table is built from the CSVs below

# 1. Load the flat shadow: one row per point. equipment_id comes from the file name
#    (BUILDING_50__AHU_1.csv -> AHU_1); everything else is a CSV column.
conn.execute(
    """CREATE TEMP TABLE point (
         timeseries_id TEXT PRIMARY KEY, point_id TEXT NOT NULL, equipment_id TEXT NOT NULL,
         owner_id TEXT, brick_class TEXT, unit TEXT, openfdd_role TEXT, source_column TEXT)"""
)
rows = []
for path in POINT_CSVS:
    equipment_id = path.stem.split("__", 1)[1]
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(
                (
                    r["timeseries_id"],
                    r["point_id"],
                    equipment_id,
                    r["owner_id"] or None,
                    r["brick_class"] or None,
                    r["unit"] or None,
                    r["openfdd_role"] or None,
                    r["source_column"],
                )
            )
conn.executemany("INSERT INTO point VALUES (?,?,?,?,?,?,?,?)", rows)
conn.execute("CREATE INDEX temp.point_role ON point (openfdd_role)")

# 2. What does one point look like? One row: the table has columns where the graph has tags.
#    (There are no markers here: the CSV never had them. The graph adds them.)
ONE_POINT_SQL = "SELECT * FROM point WHERE point_id = :point_id"
one_point = pd.read_sql_query(ONE_POINT_SQL, conn, params={"point_id": "AHU_1_DA_P"})

# 3. FC1's inputs per AHU, by role: a WHERE on the role column.
FC1_SQL = """
SELECT equipment_id, openfdd_role AS role, point_id, timeseries_id
FROM point
WHERE openfdd_role IN ('fan-status', 'duct-static-pressure', 'duct-static-pressure-sp')
ORDER BY equipment_id, openfdd_role
"""
fc1_inputs = pd.read_sql_query(FC1_SQL, conn)

# 4. How many points per AHU carry a fault-rule role at all?
ROLE_COUNT_SQL = """
SELECT equipment_id, count(openfdd_role) AS roles
FROM point
GROUP BY equipment_id
ORDER BY equipment_id
"""
roles_per_ahu = pd.read_sql_query(ROLE_COUNT_SQL, conn)

RESULTS = {"fc1_inputs": fc1_inputs, "roles_per_ahu": roles_per_ahu}

print(f"The point table has {len(rows)} rows (one per point).\n")
print("One point, as a row:")
print(one_point.T.to_string(header=False))
print("\nFC1's inputs, found by role and equipment:")
print(fc1_inputs.to_string(index=False))
print("\nPoints with a fault-rule role, per AHU:")
print(roles_per_ahu.to_string(index=False))
