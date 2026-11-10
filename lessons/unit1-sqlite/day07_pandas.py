# Day 7 (pandas): stack the two AHUs, then join them on time to compare their outside air sensors.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day07_pandas.py

import pandas as pd

# 1. Read both AHUs (same columns, different files)
columns = ["timestamp_utc", "outside_air_temp_f"]
ahu_1 = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)
ahu_2 = pd.read_csv("data/BUILDING_50/AHU_2/history_wide.csv", usecols=columns)

# 2. Stack: one table, rows of AHU_2 below the rows of AHU_1
ahu_1["equipment_id"] = "AHU_1"
ahu_2["equipment_id"] = "AHU_2"
stacked = pd.concat([ahu_1, ahu_2])

# 3. Join: one row per timestamp, one column per AHU
both = ahu_1.merge(ahu_2, on="timestamp_utc", suffixes=("_ahu_1", "_ahu_2"))

# 4. How far apart are the two sensors? (a difference in degF * 5/9 = kelvin)
diff_f = both["outside_air_temp_f_ahu_1"] - both["outside_air_temp_f_ahu_2"]
diff_k = (diff_f * 5 / 9).abs()
mean_diff_k = diff_k.mean()
rows_over_2k = (diff_k > 2).sum()
rows_over_20k = (diff_k > 20).sum()

print("Rows in the stacked table:", len(stacked))
print("Rows in the joined table: ", len(both))
print("Average gap between the sensors (K):", round(mean_diff_k, 2))
print("Rows more than 2 K apart: ", rows_over_2k)
print("Rows more than 20 K apart:", rows_over_20k)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "stacked_rows": len(stacked),
    "joined_rows": len(both),
    "mean_gap_k": mean_diff_k,
    "rows_over_2k": rows_over_2k,
    "rows_over_20k": rows_over_20k,
}
