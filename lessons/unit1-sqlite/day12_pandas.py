"""Day 12, pandas: look at neighbours and windows -- shift, rolling, and fan starts and stops.

    uv run python lessons/unit1-sqlite/day12_pandas.py

For each AHU, in time order: the previous and next duct static reading (shift), a 1-hour rolling
mean (12 rows of 5 minutes), and the rows where the supply fan starts or stops. Duct static is
converted to pascals (SI) first. Compare the printout with day12_sql.py: the numbers should match.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

PA_PER_INH2O = 249.08891  # the historian logged inches of water; the math is SI (pascals)
WINDOW_ROWS = 12  # 12 rows x 5 min = 1 hour
AHEAD_ROWS = 3  # 3 rows x 5 min = 15 minutes

# 1. Load: both AHUs, the columns we need, in (equipment, time) order.
COLUMNS = ["timestamp_utc", "supply_fan_status", "da_p_inwc"]
frames = []
for equip in ("AHU_1", "AHU_2"):
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    df.insert(0, "equipment_id", equip)
    frames.append(df)
h = pd.concat(frames, ignore_index=True)
h = h.sort_values(["equipment_id", "timestamp_utc"], ignore_index=True)

# 2. SI units
h["duct_static_pa"] = h["da_p_inwc"] * PA_PER_INH2O
eq = h["equipment_id"]
static = h.groupby(eq)["duct_static_pa"]  # groupby(eq) plays the part of PARTITION BY equipment_id
fan = h["supply_fan_status"]

# 3. LAG / LEAD are shift(+n) / shift(-n). An AHU's first row has no previous row: NaN (SQL: NULL).
h["static_prev_pa"] = static.shift(1)
h["static_next_pa"] = static.shift(-1)
h["static_ahead_pa"] = static.shift(-AHEAD_ROWS)
h["static_step_pa"] = h["duct_static_pa"] - h["static_prev_pa"]

# 4. A 1-hour rolling mean of the current row and the 11 before it. min_periods=1 lets the first
# rows use what they have (SQL's ROWS BETWEEN 11 PRECEDING does that without being asked).
h["static_1h_mean_pa"] = static.transform(lambda s: s.rolling(WINDOW_ROWS, min_periods=1).mean())

# 5. Fan starts and stops: the status changed from the previous row.
fan_prev = fan.groupby(eq).shift(1)
h["fan_start"] = ((fan == 1) & (fan_prev == 0)).astype(int)
h["fan_stop"] = ((fan == 0) & (fan_prev == 1)).astype(int)

WINDOW_COLUMNS = [
    "equipment_id",
    "timestamp_utc",
    "supply_fan_status",
    "duct_static_pa",
    "static_prev_pa",
    "static_next_pa",
    "static_ahead_pa",
    "static_step_pa",
    "static_1h_mean_pa",
    "fan_start",
    "fan_stop",
]
windows = h[WINDOW_COLUMNS]

# 6. One line per AHU: how often the fan cycles, and static 15 minutes after a start.
per_ahu = h.groupby("equipment_id").agg(
    fan_starts=("fan_start", "sum"),
    fan_stops=("fan_stop", "sum"),
    max_static_1h_mean_pa=("static_1h_mean_pa", "max"),
)
after_start = (
    h[h["fan_start"] == 1]
    .groupby("equipment_id")
    .agg(
        first_start=("timestamp_utc", "min"),
        avg_static_15min_after_start_pa=("static_ahead_pa", "mean"),
    )
)
summary = per_ahu.join(after_start).reset_index()
changed = (h["fan_start"] == 1) | (h["fan_stop"] == 1)
events = h.loc[changed, ["equipment_id", "timestamp_utc", "fan_start", "fan_stop"]]

RESULTS = {"windows": windows, "fan_summary": summary, "fan_events": events}

print("Fan cycling per AHU (duct static in Pa):")
print(summary.round(2).to_string(index=False))
print("\nFirst 6 fan events on AHU_1 (start=1 / stop=1):")
print(events[events["equipment_id"] == "AHU_1"].head(6).to_string(index=False))
sample = (
    windows[(windows["equipment_id"] == "AHU_1") & (windows["fan_start"] == 1)].head(1).index[0]
)
print("\nAround the first AHU_1 fan start:")
cols = [
    "timestamp_utc",
    "supply_fan_status",
    "duct_static_pa",
    "static_prev_pa",
    "static_1h_mean_pa",
]
print(windows.loc[sample - 2 : sample + 3, cols].round(1).to_string(index=False))
