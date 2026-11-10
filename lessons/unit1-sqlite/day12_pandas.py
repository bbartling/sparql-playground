# Day 12 (pandas): look at neighbouring rows: shift, a rolling mean, and fan starts and stops.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day12_pandas.py

import pandas as pd

PA_PER_INH2O = 249.08891  # 1 inch of water = 249.09 pascals
WINDOW_ROWS = 12  # 12 rows x 5 min = 1 hour

# 1. Read AHU_1's data, only the columns we need
columns = ["timestamp_utc", "supply_fan_status", "da_p_inwc"]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Convert duct static to pascals
df["static_pa"] = df["da_p_inwc"] * PA_PER_INH2O

# 3. shift(1) is the previous row, shift(-3) is 3 rows (15 minutes) ahead
df["static_prev_pa"] = df["static_pa"].shift(1)
df["static_ahead_pa"] = df["static_pa"].shift(-3)

# 4. Rolling mean of this row and the 11 before it = 1 hour (min_periods=1: use what exists)
df["static_1h_mean_pa"] = df["static_pa"].rolling(WINDOW_ROWS, min_periods=1).mean()

# 5. Fan start: on now, off in the previous row. Fan stop: the other way round.
fan_prev = df["supply_fan_status"].shift(1)
df["fan_start"] = ((df["supply_fan_status"] == 1) & (fan_prev == 0)).astype(int)
df["fan_stop"] = ((df["supply_fan_status"] == 0) & (fan_prev == 1)).astype(int)

# 6. Totals, and static 15 minutes after each start
fan_starts = df["fan_start"].sum()
fan_stops = df["fan_stop"].sum()
max_mean = df["static_1h_mean_pa"].max()
after_start = df[df["fan_start"] == 1]
first_start = after_start["timestamp_utc"].min()
avg_after_start = after_start["static_ahead_pa"].mean()

events = df[(df["fan_start"] == 1) | (df["fan_stop"] == 1)]
events = events[["timestamp_utc", "fan_start", "fan_stop"]]

print("AHU_1 fan cycling (duct static in Pa)")
print("  fan starts:", fan_starts)
print("  fan stops: ", fan_stops)
print("  highest 1-hour mean static (Pa):", round(max_mean, 1))
print("  first fan start:", first_start)
print("  average static 15 min after a start (Pa):", round(avg_after_start, 2))
print("First 3 fan events (start=1 or stop=1):")
print(events.head(3).to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "fan_starts": fan_starts,
    "fan_stops": fan_stops,
    "max_static_1h_mean_pa": max_mean,
    "first_start": first_start,
    "avg_static_15min_after_start_pa": avg_after_start,
    "fan_events": events,
}
