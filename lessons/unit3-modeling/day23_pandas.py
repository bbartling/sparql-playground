# Day 23 (pandas): UUIDs, the long `samples` table, and pivoting AHU_1's FC1 inputs to wide.
# Run from the repo root (once: uv run bldgts model build && uv run bldgts bootstrap):
#     uv run python lessons/unit3-modeling/day23_pandas.py
#
# var/timeseries.sqlite stores history *long*: one row per reading in
# samples(timeseries_id, ts, value), with no column names. The point list says which UUID is
# which role. Pivot long -> wide and the result must equal the CSV's own columns.

import sqlite3
import uuid

import pandas as pd

# The three inputs FC1 needs: role -> the column name we give it in the wide table
columns_for_role = {
    "fan-status": "fan_status",
    "duct-static-pressure": "duct_static_inwc",
    "duct-static-pressure-sp": "duct_static_sp_inwc",
}

# 1. The point list: which UUID is which role, and which CSV column it came from
points = pd.read_csv("model/points/BUILDING_50__AHU_1.csv")
fc1_points = points[points["openfdd_role"].isin(columns_for_role)]

# 2. Where did those UUIDs come from? A UUIDv5 is a hash of a name, so the same name always
#    gives the same id. Mint each one again from its name and compare.
uuid_rows = []
for _, point in fc1_points.iterrows():
    name = "urn:openfdd:BUILDING_50:AHU_1:" + point["source_column"]
    recomputed = str(uuid.uuid5(uuid.NAMESPACE_URL, name))
    uuid_rows.append(
        {
            "role": point["openfdd_role"],
            "source_column": point["source_column"],
            "timeseries_id": point["timeseries_id"],
            "recomputed_uuid": recomputed,
            "matches": point["timeseries_id"] == recomputed,
        }
    )
uuid_check = pd.DataFrame(uuid_rows).sort_values("role")

# 3. The long table: read each series by its UUID, one row per (timeseries_id, ts)
conn = sqlite3.connect("file:var/timeseries.sqlite?mode=ro", uri=True)  # read-only
pieces = []
for _, point in fc1_points.iterrows():
    sql = "SELECT ts, value FROM samples WHERE timeseries_id = ?"
    one_series = pd.read_sql_query(sql, conn, params=[point["timeseries_id"]])
    one_series["role"] = point["openfdd_role"]
    pieces.append(one_series)
long = pd.concat(pieces)
long_counts = long.groupby("role")["ts"].agg(rows="size", first_ts="min", last_ts="max")
long_counts = long_counts.reset_index()

# 4. Long -> wide: one row per timestamp, one column per role
wide = long.pivot(index="ts", columns="role", values="value")
wide = wide.rename(columns=columns_for_role).reset_index()
wide.columns.name = None

# 5. Compare with the CSV the history came from: same timestamps, same values?
csv = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv")
csv_times = pd.to_datetime(csv["timestamp_utc"], utc=True)
csv["ts"] = csv_times.dt.as_unit("s").astype("int64")  # epoch seconds, like samples.ts
both = csv.merge(wide, on="ts")  # keep the timestamps found in both tables

match_rows = []
for _, point in fc1_points.iterrows():
    csv_column = point["source_column"]
    wide_column = columns_for_role[point["openfdd_role"]]
    difference = (both[csv_column] - both[wide_column]).abs()
    match_rows.append(
        {
            "role": point["openfdd_role"],
            "source_column": csv_column,
            "rows_compared": len(both),
            "rows_equal": int((both[csv_column] == both[wide_column]).sum()),
            "max_abs_diff": difference.max(),
        }
    )
csv_match = pd.DataFrame(match_rows).sort_values("role")

print("The UUID of each FC1 input, and the same UUID minted again from its name:")
print(uuid_check.to_string(index=False))
print("\nLong table:", len(long), "rows for", len(fc1_points), "series.")
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
