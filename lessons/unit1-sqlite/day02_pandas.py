# Day 2 (pandas): pick columns and filter rows.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day02_pandas.py

import pandas as pd

LIMIT_INWC = 1.5  # "high" duct static pressure, in inches of water

# 1. Read only the columns we need
columns = ["timestamp_utc", "outside_air_temp_f", "da_p_inwc", "supply_fan_status"]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Pick two columns and keep the first three rows
outside_air = df[["timestamp_utc", "outside_air_temp_f"]]
first_three = outside_air.head(3)
print(first_three.to_string(index=False))

# 3. Sort by temperature; the first row is the coldest reading
sorted_rows = outside_air.sort_values(["outside_air_temp_f", "timestamp_utc"])
coldest = sorted_rows.head(1)
print("Coldest reading:")
print(coldest.to_string(index=False))

# 4. Filter rows: how many readings had duct static above the limit?
high_static = df[df["da_p_inwc"] > LIMIT_INWC]
print("Readings with static above", LIMIT_INWC, "inH2O:", len(high_static))

# 5. Two conditions: the fan is on AND static is below 0.5
fan_on = df["supply_fan_status"] == 1
static_low = df["da_p_inwc"] < 0.5
fan_on_low = df[fan_on & static_low]
print("Fan on but static below 0.5 inH2O:", len(fan_on_low))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "first_three": first_three,
    "coldest": coldest,
    "high_static": len(high_static),
    "fan_on_low": len(fan_on_low),
}
