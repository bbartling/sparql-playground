# Day 10 (pandas): Open-FDD events. Episodes per rule, then which rows fall inside an episode.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day10_pandas.py

import pandas as pd

# 1. Read Open-FDD's episodes for AHU_1 (one row per stretch of time a rule was in fault)
events = pd.read_csv("data/BUILDING_50/AHU_1/fdd_events.csv")

# 2. Count episodes and add up their minutes, per rule
per_rule = events.groupby("rule_name").agg(
    episodes=("rule_name", "size"), duration_min=("duration_min", "sum")
)
per_rule = per_rule.reset_index()
per_rule["hours"] = per_rule["duration_min"] / 60
per_rule = per_rule[["rule_name", "episodes", "hours"]]

# 3. Read AHU_1's history, and look at one rule's episodes
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=["timestamp_utc"])
fc13_events = events[events["rule_name"] == "fc13"]

# 4. Mark the rows inside each episode (start <= time <= end). The timestamps are text in
#    one format, so comparing the text compares the times.
df["in_episode"] = False
for _, event in fc13_events.iterrows():
    after_start = df["timestamp_utc"] >= event["start_time_utc"]
    before_end = df["timestamp_utc"] <= event["end_time_utc"]
    df.loc[after_start & before_end, "in_episode"] = True

# 5. Each row is 5 minutes, so rows x 5 / 60 = hours
rows_in_episode = df["in_episode"].sum()
covered_hours = rows_in_episode * 5 / 60
summed_hours = per_rule[per_rule["rule_name"] == "fc13"]["hours"].iloc[0]

print(per_rule.round(1).to_string(index=False))
print("fc13 rows inside an episode:", rows_in_episode)
print("Hours those rows cover (5 min each):", round(covered_hours, 1))
print("Hours if you add up every episode:  ", round(summed_hours, 1), "(episodes overlap)")

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "per_rule": per_rule,
    "rows_in_episode": rows_in_episode,
    "covered_hours": covered_hours,
    "summed_hours": summed_hours,
}
