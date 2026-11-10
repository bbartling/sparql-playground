# Day 14 (pandas): fault rule FC1, "duct static pressure too low while the fan runs".
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day14_pandas.py

import pandas as pd

# Rule settings
PA_PER_INH2O = 249.08891  # 1 inch of water = 249.09 pascals
TOLERANCE_PA = 25  # how far below setpoint counts as "too low"
CONFIRM_ROWS = 2  # the fault must last 2 rows in a row (2 x 5 min = 10 minutes)

# 1. Read AHU_1's data, only the columns this rule needs
columns = ["timestamp_utc", "supply_fan_status", "da_p_inwc", "da_p_setpoint_inwc"]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Convert the pressures to pascals (fault math is SI)
df["static_pa"] = df["da_p_inwc"] * PA_PER_INH2O
df["setpoint_pa"] = df["da_p_setpoint_inwc"] * PA_PER_INH2O

# 3. Raw fault: the fan is on AND static is more than 25 Pa below setpoint
fan_on = df["supply_fan_status"] == 1
too_low = df["static_pa"] < df["setpoint_pa"] - TOLERANCE_PA
df["raw_fault"] = fan_on & too_low

# 4. Confirm: number each "streak" of equal values, then count rows inside each streak
df["new_streak"] = df["raw_fault"] != df["raw_fault"].shift()  # True where the value changes
df["streak_id"] = df["new_streak"].cumsum()
df["row_in_streak"] = df.groupby("streak_id").cumcount() + 1
df["fault"] = df["raw_fault"] & (df["row_in_streak"] >= CONFIRM_ROWS)

# 5. Totals: each row is 5 minutes, so rows x 5 / 60 = hours
raw_hours = df["raw_fault"].sum() * 5 / 60
fault_hours = df["fault"].sum() * 5 / 60
episodes = df[df["fault"]]["streak_id"].nunique()

# 6. Open-FDD's results for the same data, and how many of its FC1 episodes we also found
events = pd.read_csv("data/BUILDING_50/AHU_1/fdd_events.csv")
fc1_events = events[events["rule_name"] == "fc1"]
openfdd_hours = fc1_events["duration_min"].sum() / 60

fault_times = df[df["fault"]]["timestamp_utc"]
found = 0
for _, event in fc1_events.iterrows():
    inside = (fault_times >= event["start_time_utc"]) & (fault_times <= event["end_time_utc"])
    if inside.any():
        found += 1

print("AHU_1, FC1 (duct static too low)")
print("  raw fault hours:      ", round(raw_hours, 2))
print("  confirmed fault hours:", round(fault_hours, 2))
print("  confirmed episodes:   ", episodes)
print("Open-FDD, FC1 on AHU_1")
print("  episodes:", len(fc1_events))
print("  hours:   ", round(openfdd_hours, 1))
print("Open-FDD episodes that contain one of our faults:", found, "of", len(fc1_events))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "raw_hours": raw_hours,
    "fault_hours": fault_hours,
    "episodes": episodes,
    "openfdd_episodes": len(fc1_events),
    "overlap": found,
}
