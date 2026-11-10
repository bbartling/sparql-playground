# Day 23 (SQL): UUIDs, the long `samples` table, and pivoting AHU_1's FC1 inputs to wide.
# Run from the repo root (once: uv run python lessons/course.py setup, and
# uv run bldgts model build && uv run bldgts bootstrap):
#     uv run python lessons/unit3-modeling/day23_sql.py
#
# var/timeseries.sqlite stores history *long*: one row per reading in
# samples(timeseries_id, ts, value), with no column names. The point list says which UUID is
# which role. Pivot long -> wide and the result must equal the CSV's own columns.

import sqlite3
import uuid

import pandas as pd

# Two database files, side by side: the API's samples (opened read-only) and the lessons'
# CSV rows. Tables we make here are TEMP tables: they vanish when the script ends.
conn = sqlite3.connect("file:var/timeseries.sqlite?mode=ro", uri=True)
conn.execute("ATTACH DATABASE 'var/lessons.sqlite' AS les")

# The three inputs FC1 needs: role -> the column name we give it in the wide table
columns_for_role = {
    "fan-status": "fan_status",
    "duct-static-pressure": "duct_static_inwc",
    "duct-static-pressure-sp": "duct_static_sp_inwc",
}

# 1. The point list goes into a TEMP table `point`: which UUID is which role
points = pd.read_csv("model/points/BUILDING_50__AHU_1.csv")
fc1_points = points[points["openfdd_role"].isin(columns_for_role)]
fc1_points = fc1_points[["openfdd_role", "source_column", "timeseries_id"]]
fc1_points = fc1_points.rename(columns={"openfdd_role": "role"})
conn.execute("CREATE TEMP TABLE point (role TEXT, source_column TEXT, timeseries_id TEXT)")
for _, point in fc1_points.iterrows():
    conn.execute(
        "INSERT INTO point VALUES (?, ?, ?)",
        [point["role"], point["source_column"], point["timeseries_id"]],
    )

# 2. Where did those UUIDs come from? A UUIDv5 is a hash of a name, so the same name always
#    gives the same id. SQLite has no SHA-1, so Python mints each one again from its name.
uuid_rows = []
for _, point in fc1_points.iterrows():
    name = "urn:openfdd:BUILDING_50:AHU_1:" + point["source_column"]
    recomputed = str(uuid.uuid5(uuid.NAMESPACE_URL, name))
    uuid_rows.append(
        {
            "role": point["role"],
            "source_column": point["source_column"],
            "timeseries_id": point["timeseries_id"],
            "recomputed_uuid": recomputed,
            "matches": point["timeseries_id"] == recomputed,
        }
    )
uuid_check = pd.DataFrame(uuid_rows).sort_values("role")

# 3. The long table: how many rows does each series have?
long_counts_sql = """
SELECT p.role, COUNT(*) AS rows, MIN(s.ts) AS first_ts, MAX(s.ts) AS last_ts
FROM samples AS s
JOIN point AS p ON p.timeseries_id = s.timeseries_id
GROUP BY p.role
ORDER BY p.role
"""
long_counts = pd.read_sql_query(long_counts_sql, conn)

# 4. Long -> wide: one row per timestamp, one column per role.
#    MAX(CASE ...) picks the one value each series has at that timestamp.
wide_sql = """
CREATE TEMP TABLE wide AS
SELECT s.ts,
       MAX(CASE WHEN p.role = 'fan-status'              THEN s.value END) AS fan_status,
       MAX(CASE WHEN p.role = 'duct-static-pressure'    THEN s.value END) AS duct_static_inwc,
       MAX(CASE WHEN p.role = 'duct-static-pressure-sp' THEN s.value END) AS duct_static_sp_inwc
FROM samples AS s
JOIN point AS p ON p.timeseries_id = s.timeseries_id
GROUP BY s.ts
"""
conn.execute(wide_sql)
wide = pd.read_sql_query("SELECT * FROM wide ORDER BY ts", conn)

# 5. Compare with the CSV the history came from (the table les.ahu_1): same values?
#    Column names can't be ? parameters, so they are pasted into the SQL text. They come
#    from our own point list, not from a user.
match_rows = []
for _, point in fc1_points.iterrows():
    csv_column = point["source_column"]
    wide_column = columns_for_role[point["role"]]
    compare_sql = f"""
        SELECT COUNT(*),
               SUM(c.{csv_column} = w.{wide_column}),
               MAX(ABS(c.{csv_column} - w.{wide_column}))
        FROM les.ahu_1 AS c
        JOIN wide AS w ON w.ts = unixepoch(c.timestamp_utc)  -- the time text as epoch seconds
    """
    rows_compared, rows_equal, max_abs_diff = conn.execute(compare_sql).fetchone()
    match_rows.append(
        {
            "role": point["role"],
            "source_column": csv_column,
            "rows_compared": rows_compared,
            "rows_equal": rows_equal,
            "max_abs_diff": max_abs_diff,
        }
    )
csv_match = pd.DataFrame(match_rows).sort_values("role")

print("The UUID of each FC1 input, and the same UUID minted again from its name:")
print(uuid_check.to_string(index=False))
print("\nLong table:", long_counts["rows"].sum(), "rows for", len(fc1_points), "series.")
print(long_counts.to_string(index=False))
print("\nWide table:", len(wide), "rows, one per timestamp. First rows:")
print(wide.head(3).to_string(index=False))
print("\nCompared with the CSV's own columns:")
print(csv_match.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "uuid_check": uuid_check,
    "long_counts": long_counts,
    "wide": wide,
    "csv_match": csv_match,
}
