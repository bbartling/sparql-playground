"""Day 23, pandas: stable UUIDs, the long `samples` table, and pivoting AHU_1's FC1 inputs to wide.

    uv run python lessons/unit3-modeling/day23_pandas.py

Needs var/timeseries.sqlite (the API's database: `uv run bldgts model build && uv run bldgts
bootstrap`). It stores history *long*: one row per reading in samples(timeseries_id, ts, value),
with no column names. The point list says which UUID is which role. Pivot long -> wide and the
result must equal the CSV columns. Compare the printout with day23_sql.py: the numbers should
match."""

import sqlite3
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"
POINTS = ROOT / "model" / "points" / "BUILDING_50__AHU_1.csv"
SAMPLES_DB = ROOT / "var" / "timeseries.sqlite"
if not SAMPLES_DB.exists():
    raise SystemExit(
        f"{SAMPLES_DB} not found. Run:  uv run bldgts model build && uv run bldgts bootstrap"
    )

BUILDING, EQUIP = "BUILDING_50", "AHU_1"
ROLE_NAMES = {  # FC1's input contract: role -> the column name the rule uses
    "fan-status": "fan_status",
    "duct-static-pressure": "duct_static_inwc",
    "duct-static-pressure-sp": "duct_static_sp_inwc",
}

# 1. The point list: which UUID is which role, and which CSV column it came from.
pts = pd.read_csv(POINTS, usecols=["openfdd_role", "source_column", "timeseries_id"])
pts = pts[pts["openfdd_role"].isin(ROLE_NAMES)].copy()
pts["column"] = pts["openfdd_role"].map(ROLE_NAMES)
pts = pts.rename(columns={"openfdd_role": "role"}).sort_values("role", ignore_index=True)


# 2. Where did those UUIDs come from? A UUIDv5 (RFC 9562) is a SHA-1 hash of a namespace and a name.
#    The same name always gives the same id, on any machine, with no registry. Build's rule:
def mint(building: str, equipment: str, source_column: str) -> str:
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"urn:openfdd:{building}:{equipment}:{source_column}")
    )


pts["recomputed_uuid"] = [mint(BUILDING, EQUIP, c) for c in pts["source_column"]]
uuid_check = pts[["role", "source_column", "timeseries_id", "recomputed_uuid"]].assign(
    matches=pts["timeseries_id"] == pts["recomputed_uuid"]
)

# 3. The long table: one row per (timeseries_id, ts). Only the three UUIDs we asked the model for.
marks = ",".join("?" * len(pts))
conn = sqlite3.connect(f"file:{SAMPLES_DB.as_posix()}?mode=ro", uri=True)
long = pd.read_sql_query(
    f"SELECT timeseries_id, ts, value FROM samples WHERE timeseries_id IN ({marks})",
    conn,
    params=list(pts["timeseries_id"]),
)
long = long.merge(pts[["timeseries_id", "role", "column"]], on="timeseries_id")
long_counts = (
    long.groupby("role")
    .agg(rows=("value", "size"), first_ts=("ts", "min"), last_ts=("ts", "max"))
    .reset_index()
)

# 4. Long -> wide: one row per timestamp, one column per role. pivot() raises if a (ts, role) pair
#    repeats, which is a useful check that the series really have one value per timestamp.
wide = long.pivot(index="ts", columns="column", values="value").reset_index()
wide.columns.name = None
wide = wide[["ts", *ROLE_NAMES.values()]].sort_values("ts", ignore_index=True)

# 5. Compare with the CSV the history came from: same timestamps, same values?
csv_cols = list(pts["source_column"])
csv = pd.read_csv(DATA / EQUIP / "history_wide.csv", usecols=["timestamp_utc", *csv_cols])
csv["ts"] = pd.to_datetime(csv["timestamp_utc"], utc=True).dt.as_unit("s").astype("int64")
both = csv.merge(wide, on="ts", how="inner")
csv_match = pd.DataFrame(
    [
        {
            "role": r.role,
            "source_column": r.source_column,
            "rows_compared": len(both),
            "rows_equal": int((both[r.source_column] == both[r.column]).sum()),
            "max_abs_diff": float((both[r.source_column] - both[r.column]).abs().max()),
        }
        for r in pts.itertuples()
    ]
)

RESULTS = {
    "uuid_check": uuid_check,
    "long_counts": long_counts,
    "wide": wide,
    "csv_match": csv_match,
}

print("The UUID of each FC1 input, and the same UUID minted again from its name:")
print(uuid_check.to_string(index=False))
print(f"\nLong table: {len(long):,} rows for {len(pts)} series.")
print(long_counts.to_string(index=False))
print(f"\nWide table: {len(wide):,} rows, one per timestamp. First rows:")
print(wide.head(3).to_string(index=False))
print("\nCompared with the CSV's own columns:")
print(csv_match.to_string(index=False))
