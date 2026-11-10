# Day 13 (pandas): streaks. The longest fan run, and "true for 6 rows in a row".
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day13_pandas.py

import pandas as pd

FULL_SPEED_PCT = 95  # "at or near full speed"
CONFIRM_ROWS = 6  # 6 rows x 5 min = 30 minutes

# 1. Read AHU_1's data, only the columns we need
columns = ["timestamp_utc", "supply_fan_status", "supply_fan_speed_pct"]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Number the streaks of the fan status: a new streak starts wherever the value changes
fan = df["supply_fan_status"]
fan_streak_id = (fan != fan.shift()).cumsum()

# 3. Each streak where the fan is on is one fan run: its start time and how many rows long
fan_on = df[fan == 1]
runs = fan_on.groupby(fan_streak_id).agg(
    start_utc=("timestamp_utc", "min"),
    rows=("timestamp_utc", "count"),
)
runs["hours"] = runs["rows"] * 5 / 60

# 4. The longest run (idxmax gives the first one if two runs tie)
longest = runs.loc[runs["rows"].idxmax()]

# 5. "Full speed for 6 rows in a row": raw flag, then streak numbers, then row-in-streak
raw = (fan == 1) & (df["supply_fan_speed_pct"] >= FULL_SPEED_PCT)
raw_streak_id = (raw != raw.shift()).cumsum()
row_in_streak = raw.groupby(raw_streak_id).cumcount() + 1
confirmed = raw & (row_in_streak >= CONFIRM_ROWS)
episodes = raw_streak_id[confirmed].nunique()

# 6. The other route: a rolling sum of the last 6 flags equals 6 only if all six were true
rolling_sum = raw.astype(int).rolling(CONFIRM_ROWS).sum()
confirmed_window = rolling_sum == CONFIRM_ROWS

print("AHU_1 fan runs (status = 1)")
print("  runs:", len(runs))
print("  average run (hours):", round(runs["hours"].mean(), 2))
print("  longest run (rows):", longest["rows"])
print("  longest run (hours):", round(longest["hours"], 2))
print("  longest run started:", longest["start_utc"])
print("Full speed (>= 95 %) for 6 rows in a row")
print("  raw rows:", raw.sum())
print("  confirmed rows (streak route):", confirmed.sum())
print("  confirmed rows (rolling route):", confirmed_window.sum())
print("  episodes:", episodes)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "runs": len(runs),
    "avg_run_hours": runs["hours"].mean(),
    "longest_rows": longest["rows"],
    "longest_hours": longest["hours"],
    "longest_start": longest["start_utc"],
    "raw_rows": raw.sum(),
    "confirmed_rows_streak": confirmed.sum(),
    "confirmed_rows_window": confirmed_window.sum(),
    "episodes": episodes,
}
