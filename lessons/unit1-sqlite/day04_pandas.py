"""Day 4, pandas: summary statistics (count, min, max, mean, sum) and fan run hours.

    uv run python lessons/unit1-sqlite/day04_pandas.py

One column in, one number out. The status point supply_fan_status is 1 when the fan runs and 0 when
it is off; with a reading every 5 minutes, sum(status) * 5 / 60 is the run hours.
Compare the printout with day04_sql.py: the numbers should match.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

# 1. Load the columns we summarize, for both AHUs. Same column names in both exports.
COLUMNS = [
    "timestamp_utc",
    "outside_air_temp_f",
    "da_p_inwc",
    "da_p_setpoint_inwc",
    "supply_fan_status",
]
frames = {
    e: pd.read_csv(DATA / e / "history_wide.csv", usecols=COLUMNS) for e in ("AHU_1", "AHU_2")
}
ahu_1 = frames["AHU_1"]

# 2. AHU_1 outside air temperature, whole dataset: four statistics, unrounded.
v = ahu_1["outside_air_temp_f"]
oat_summary = pd.DataFrame(
    {
        "n": [len(v)],
        "n_values": [v.count()],
        "min_f": [v.min()],
        "max_f": [v.max()],
        "avg_f": [v.mean()],
    }
)

# 3. The same for one day: a mask first (Day 2's half-open range on the ISO text), then stats.
START, END = "2026-07-01 00:00:00+00:00", "2026-07-02 00:00:00+00:00"
day = ahu_1[(ahu_1["timestamp_utc"] >= START) & (ahu_1["timestamp_utc"] < END)][
    "outside_air_temp_f"
]
oat_july_1 = pd.DataFrame({"min_f": [day.min()], "max_f": [day.max()], "avg_f": [day.mean()]})

# 4. Run hours of the supply fan, per AHU: sum of a 0/1 column x 5 minutes / 60.
run_hours = pd.DataFrame(
    {
        "equipment_id": list(frames),
        "run_hours": [f["supply_fan_status"].sum() * 5 / 60 for f in frames.values()],
        "fraction_running": [f["supply_fan_status"].mean() for f in frames.values()],
    }
)

# 5. Averages that mislead: static pressure averaged over ALL hours, fan on and off.
averages = pd.DataFrame(
    {
        "static_inwc": [ahu_1["da_p_inwc"].mean()],
        "static_setpoint_inwc": [ahu_1["da_p_setpoint_inwc"].mean()],
    }
)

# 6. NULLs: pandas stores a missing value as NaN and skips it. (The real columns have none.)
t = pd.Series([1.0, np.nan, 3.0])
null_demo = pd.DataFrame({"n_rows": [len(t)], "n_values": [t.count()], "mean": [t.mean()]})

# 7. Integer division: Python 3's / is always true division; // is the one that drops the rest.
division = pd.DataFrame({"floor_div": [7 * 5 // 60], "true_div": [7 * 5 / 60]})

RESULTS = {
    "oat_summary": oat_summary,
    "oat_july_1": oat_july_1,
    "run_hours": run_hours,
    "averages": averages,
    "null_demo": null_demo,
    "division": division,
}

print("AHU_1 outside air temperature, whole dataset:")
print(oat_summary.round({"min_f": 2, "max_f": 2, "avg_f": 3}).to_string(index=False))
print("\nthe same for 2026-07-01:")
print(oat_july_1.round(1).to_string(index=False))
print("\nsupply fan run hours (readings with the fan on x 5 min / 60):")
print(run_hours.round(3).to_string(index=False))
print("\nAHU_1 duct static and its setpoint, averaged over every hour (inH2O):")
print(averages.round(3).to_string(index=False))
print("\nthree values, one missing:")
print(null_demo.round(3).to_string(index=False))
print("\n7 * 5 / 60 two ways (floor, true):", division.iloc[0].round(4).tolist())
