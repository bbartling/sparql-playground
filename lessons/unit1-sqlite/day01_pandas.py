"""Day 1, pandas: open AHU_1's CSV export and see what one row is.

    uv run python lessons/unit1-sqlite/day01_pandas.py

The historian's export is a "wide" table: one row per timestamp, one column per point.
read_csv gives it to you as a DataFrame; shape, columns and dtypes say what you are holding.
Compare the printout with day01_sql.py: the numbers should match.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

# 1. Open AHU_1: every column (usecols is for later days; today the point is to see them all).
ahu_1 = pd.read_csv(DATA / "AHU_1" / "history_wide.csv")

# 2. Shape: (rows, columns). AHU_2 is a different air handler with a different set of points.
ahu_2 = pd.read_csv(DATA / "AHU_2" / "history_wide.csv")
shapes = pd.DataFrame(
    {
        "equipment_id": ["AHU_1", "AHU_2"],
        "rows": [len(ahu_1), len(ahu_2)],
        "columns": [ahu_1.shape[1], ahu_2.shape[1]],
    }
)

# 3. Columns: position and name (the DataFrame's version of PRAGMA table_info).
columns = pd.DataFrame({"cid": range(ahu_1.shape[1]), "name": ahu_1.columns})
dtype_counts = ahu_1.dtypes.astype(
    str
).value_counts()  # timestamp is text (object), the rest float64

# 4. The first rows, a few columns. One row = one moment; each column = one point's value then.
SHOW = [
    "timestamp_utc",
    "outside_air_temp_f",
    "da_p_inwc",
    "da_p_setpoint_inwc",
    "supply_fan_status",
]
first_rows = ahu_1[SHOW].head(5)

# 5. One row per timestamp: no duplicates, and the time span the export covers.
time_span = pd.DataFrame(
    {
        "first_utc": [ahu_1["timestamp_utc"].min()],
        "last_utc": [ahu_1["timestamp_utc"].max()],
        "distinct_timestamps": [ahu_1["timestamp_utc"].nunique()],
    }
)

# 6. What each column is: columns.csv sits next to the history (it is not loaded into SQLite).
meta = pd.read_csv(DATA / "AHU_1" / "columns.csv")
described = meta[meta["col"].isin(SHOW[1:])][["col", "point_name"]]

RESULTS = {
    "shapes": shapes,
    "columns": columns,
    "first_rows": first_rows,
    "time_span": time_span,
}

print("1. rows x columns per AHU:")
print(shapes.to_string(index=False))
print("\n2. AHU_1 dtypes (how many columns of each kind):")
print(dtype_counts.to_string())
print("\n3. the first and last five column names:")
print(columns.iloc[[*range(5), *range(-5, 0)]].to_string(index=False))
print("\n4. the first five rows, five columns:")
print(first_rows.to_string(index=False))
print("\n5. time span:")
print(time_span.to_string(index=False))
print("\n6. what the columns mean (from columns.csv):")
print(described.to_string(index=False))
