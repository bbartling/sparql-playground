"""Day 6, pandas: convert AHU_1's FDD columns from US units to SI (degC, Pa, fractions 0-1).

    uv run python lessons/unit1-sqlite/day06_pandas.py

Fault math is SI-only, like Open-FDD's. The BAS logged degF, inches of water and percent 0-100, so
the first step of every rule is a conversion. `assign` adds the converted columns next to the raw
ones.
Compare the printout with day06_sql.py: the numbers should match.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

PA_PER_INH2O = 249.08891  # 1 inch of water column = 249.08891 pascals

# 1. Load: only the columns we convert
COLUMNS = [
    "timestamp_utc",
    "discharge_air_temp_f",
    "dat_reset_f",
    "outside_air_temp_f",
    "da_p_inwc",
    "da_p_setpoint_inwc",
    "supply_fan_speed_pct",
    "chw_valve_pct",
]
raw = pd.read_csv(DATA / "AHU_1" / "history_wide.csv", usecols=COLUMNS)[COLUMNS]

# 2. Convert. Absolute temperatures use (F - 32) * 5/9. Pressure is a plain factor. Percent is /
#    100.
si = raw[["timestamp_utc"]].assign(
    discharge_air_temp_c=(raw["discharge_air_temp_f"] - 32) * 5 / 9,
    dat_setpoint_c=(raw["dat_reset_f"] - 32) * 5 / 9,
    outside_air_temp_c=(raw["outside_air_temp_f"] - 32) * 5 / 9,
    duct_static_pa=raw["da_p_inwc"] * PA_PER_INH2O,
    duct_static_sp_pa=raw["da_p_setpoint_inwc"] * PA_PER_INH2O,
    supply_fan_speed_frac=raw["supply_fan_speed_pct"] / 100,
    chw_valve_frac=raw["chw_valve_pct"] / 100,
)

# 3. The delta trap: DAT error is a temperature DIFFERENCE. A difference has no 32 in it: x degF =
#    x * 5/9 K.
#    Right: convert the difference, or subtract two converted values (same answer).
#    Wrong: push the difference through the absolute formula.
delta_f = raw["discharge_air_temp_f"] - raw["dat_reset_f"]
deltas = raw[["timestamp_utc"]].assign(
    dat_error_k=delta_f * 5 / 9,
    dat_error_k_check=si["discharge_air_temp_c"] - si["dat_setpoint_c"],
    dat_error_wrong=(delta_f - 32) * 5 / 9,
)

# 4. Summaries: means in SI, and the 5 degF demo
means = si.drop(columns="timestamp_utc").mean().to_frame("mean").rename_axis("column").reset_index()
five_f = pd.DataFrame({"delta_f": [5.0], "right_k": [5 * 5 / 9], "wrong_k": [(5 - 32) * 5 / 9]})

RESULTS = {"ahu_1_si": si, "dat_error": deltas, "si_means": means, "five_f": five_f}

print("A 5 degF *difference*:")
print(five_f.round(2).to_string(index=False))
print("\nFirst rows, US units then SI:")
print(raw.head(3).round(2).to_string(index=False))
print(si.head(3).round(2).to_string(index=False))
print("\nMean of each SI column:")
print(means.round(3).to_string(index=False))
print("\nDAT error (K), right vs wrong, over all rows:")
print(deltas[["dat_error_k", "dat_error_wrong"]].describe().loc[["mean", "min", "max"]].round(2))
