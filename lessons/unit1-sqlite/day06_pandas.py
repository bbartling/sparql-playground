# Day 6 (pandas): convert AHU_1's US units to SI (degC, Pa, fractions 0-1).
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day06_pandas.py

import pandas as pd

PA_PER_INH2O = 249.08891  # 1 inch of water = 249.09 pascals

# 1. Read AHU_1's data, only the columns we convert
columns = [
    "discharge_air_temp_f",
    "dat_reset_f",
    "outside_air_temp_f",
    "da_p_inwc",
    "supply_fan_speed_pct",
]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Convert each column to SI
df["discharge_air_temp_c"] = (df["discharge_air_temp_f"] - 32) * 5 / 9  # a temperature: minus 32
df["outside_air_temp_c"] = (df["outside_air_temp_f"] - 32) * 5 / 9
df["duct_static_pa"] = df["da_p_inwc"] * PA_PER_INH2O  # a pressure: multiply
df["supply_fan_speed_frac"] = df["supply_fan_speed_pct"] / 100  # percent -> 0 to 1

# 3. A temperature DIFFERENCE has no 32 in it: x degF is x * 5 / 9 kelvin
dat_error_f = df["discharge_air_temp_f"] - df["dat_reset_f"]
dat_error_k = dat_error_f * 5 / 9
dat_error_wrong_k = (dat_error_f - 32) * 5 / 9  # the common mistake

# 4. Averages in SI
dat_c = df["discharge_air_temp_c"].mean()
oat_c = df["outside_air_temp_c"].mean()
static_pa = df["duct_static_pa"].mean()
fan_speed = df["supply_fan_speed_frac"].mean()
error_k = dat_error_k.mean()
error_wrong_k = dat_error_wrong_k.mean()

print("Average discharge air temperature (C):", round(dat_c, 3))
print("Average outside air temperature (C):  ", round(oat_c, 3))
print("Average duct static pressure (Pa):    ", round(static_pa, 3))
print("Average supply fan speed (fraction):  ", round(fan_speed, 3))
print("Average DAT error, right (K):         ", round(error_k, 3))
print("Average DAT error, wrong (K):         ", round(error_wrong_k, 3))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "dat_c": dat_c,
    "oat_c": oat_c,
    "static_pa": static_pa,
    "fan_speed_frac": fan_speed,
    "dat_error_k": error_k,
    "dat_error_wrong_k": error_wrong_k,
}
