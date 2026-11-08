"""Day 1, SQL: the same AHU_1 export, loaded as the SQLite table `ahu_1`.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day01_sql.py

setup_db.py made one table per CSV: same column names, same values, nothing transformed. This script
asks SQLite what it holds. SQLite does all the work; pandas only turns the result rows into a table
for printing.
Compare the printout with day01_pandas.py: the numbers should match.
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)

# 1. The table's structure comes from SQLite's own catalog. PRAGMA table_info lists the columns.
TABLE_INFO_SQL = "PRAGMA table_info(ahu_1)"  # cid, name, declared type, notnull, default, pk

# 2. Shape: count(*) rows, and count the rows PRAGMA table_info would return for the column count.
SHAPES_SQL = """
SELECT 'AHU_1' AS equipment_id,
       (SELECT count(*) FROM ahu_1) AS rows,
       (SELECT count(*) FROM pragma_table_info('ahu_1')) AS columns
UNION ALL
SELECT 'AHU_2',
       (SELECT count(*) FROM ahu_2),
       (SELECT count(*) FROM pragma_table_info('ahu_2'))
"""

# 3. Columns: position and name. pragma_table_info() is PRAGMA table_info as a selectable table.
COLUMNS_SQL = "SELECT cid, name FROM pragma_table_info('ahu_1') ORDER BY cid"
TYPE_COUNTS_SQL = "SELECT type, count(*) AS columns FROM pragma_table_info('ahu_1') GROUP BY type"

# 4. The first rows, a few columns. Without ORDER BY SQL promises no order, so sort by the key.
FIRST_ROWS_SQL = """
SELECT timestamp_utc, outside_air_temp_f, da_p_inwc, da_p_setpoint_inwc, supply_fan_status
FROM ahu_1
ORDER BY timestamp_utc
LIMIT 5
"""

# 5. One row per timestamp: the PRIMARY KEY forbids duplicates; this counts them anyway.
TIME_SPAN_SQL = """
SELECT min(timestamp_utc) AS first_utc,
       max(timestamp_utc) AS last_utc,
       count(DISTINCT timestamp_utc) AS distinct_timestamps
FROM ahu_1
"""

table_info = pd.read_sql_query(TABLE_INFO_SQL, conn)
shapes = pd.read_sql_query(SHAPES_SQL, conn)
columns = pd.read_sql_query(COLUMNS_SQL, conn)
type_counts = pd.read_sql_query(TYPE_COUNTS_SQL, conn)
first_rows = pd.read_sql_query(FIRST_ROWS_SQL, conn)
time_span = pd.read_sql_query(TIME_SPAN_SQL, conn)

# 6. columns.csv (what each column means) is a file next to the history, not a table here.

RESULTS = {
    "shapes": shapes,
    "columns": columns,
    "first_rows": first_rows,
    "time_span": time_span,
}

print("1. PRAGMA table_info(ahu_1), some rows (cid, name, declared type, notnull, default, pk):")
print(table_info.iloc[[0, 1, 2, -2, -1]].to_string(index=False))
print("\n2. rows x columns per AHU:")
print(shapes.to_string(index=False))
print("\n   declared types (how many columns of each kind):")
print(type_counts.to_string(index=False))
print("\n3. the first and last five column names:")
print(columns.iloc[[*range(5), *range(-5, 0)]].to_string(index=False))
print("\n4. the first five rows, five columns:")
print(first_rows.to_string(index=False))
print("\n5. time span:")
print(time_span.to_string(index=False))
