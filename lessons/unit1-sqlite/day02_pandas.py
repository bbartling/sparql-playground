"""Day 2, pandas: pick columns, filter rows, sort and trim, on AHU_1.

    uv run python lessons/unit1-sqlite/day02_pandas.py

SELECT = df[[...]], WHERE = a boolean mask, ORDER BY = sort_values, LIMIT = head.
Column names are hard-coded on purpose: this is how a first FDD script looks. (Week 5 replaces
them with a model lookup.)
Compare the printout with day02_sql.py: the numbers should match.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

# 1. Load only the columns today's questions use.
COLUMNS = [
    "timestamp_utc",
    "outside_air_temp_f",
    "da_p_inwc",
    "da_p_setpoint_inwc",
    "supply_fan_status",
]
df = pd.read_csv(DATA / "AHU_1" / "history_wide.csv", usecols=COLUMNS)

# 2. SELECT a few columns, ORDER BY time, LIMIT 3: the first three outside air readings.
first3 = (
    df[["timestamp_utc", "outside_air_temp_f"]].sort_values("timestamp_utc").head(3)
).reset_index(drop=True)

# 3. Hottest and coldest reading: sort by value, keep one row. The second sort key breaks ties.
hottest = (
    df[["timestamp_utc", "outside_air_temp_f"]]
    .sort_values(["outside_air_temp_f", "timestamp_utc"], ascending=[False, True])
    .head(1)
    .reset_index(drop=True)
)
coldest = (
    df[["timestamp_utc", "outside_air_temp_f"]]
    .sort_values(["outside_air_temp_f", "timestamp_utc"])
    .head(1)
    .reset_index(drop=True)
)

# 4. WHERE with a limit that is a variable (SQL binds it as a parameter): static above 1.5 inH2O.
LIMIT_INWC = 1.5
high_static = pd.DataFrame({"n": [int((df["da_p_inwc"] > LIMIT_INWC).sum())]})

# 5. Two conditions: fan running AND hot outside. Hottest five such rows.
MIN_OAT_F = 95.0
hot_running = (
    df[(df["supply_fan_status"] == 1) & (df["outside_air_temp_f"] > MIN_OAT_F)][
        ["timestamp_utc", "outside_air_temp_f", "da_p_inwc"]
    ]
    .sort_values(["outside_air_temp_f", "timestamp_utc"], ascending=[False, True])
    .head(5)
    .reset_index(drop=True)
)

# 6. A time range. The timestamps are ISO text in one format, so string comparison is time order.
START, END = "2026-07-01 00:00:00+00:00", "2026-07-02 00:00:00+00:00"
july_1 = pd.DataFrame(
    {"n": [int(((df["timestamp_utc"] >= START) & (df["timestamp_utc"] < END)).sum())]}
)

# 7. Hostile input is just a string that matches nothing (SQL: it travels as a parameter).
EVIL = "x' OR '1'='1"
hostile = pd.DataFrame({"n": [int((df["timestamp_utc"] == EVIL).sum())]})

# 8. Which values does a status point take? (DISTINCT)
fan_values = pd.DataFrame({"fan_status": sorted(df["supply_fan_status"].unique())})

RESULTS = {
    "first3": first3,
    "hottest": hottest,
    "coldest": coldest,
    "high_static": high_static,
    "hot_running": hot_running,
    "july_1": july_1,
    "hostile": hostile,
    "fan_values": fan_values,
}

print("first three outside air readings:")
print(first3.to_string(index=False))
print("\nhottest / coldest reading:")
print(pd.concat([hottest, coldest]).round(2).to_string(index=False))
print(f"\nreadings with duct static above {LIMIT_INWC} inH2O:", high_static["n"][0])
print(f"\nhottest five readings above {MIN_OAT_F} F with the fan on:")
print(hot_running.round(3).to_string(index=False))
print("\nreadings on 2026-07-01 (UTC):", july_1["n"][0])
print("rows matching a hostile string:", hostile["n"][0])
print("fan status takes the values:", fan_values["fan_status"].tolist())
