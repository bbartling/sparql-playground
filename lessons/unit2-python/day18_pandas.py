# Day 18 (pandas): FC1 on data with holes: sample-and-hold, a gap limit, and coverage.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day18_pandas.py

import pandas as pd

START_TS = 1_773_619_200  # the synthetic data's first timestamp (epoch seconds)
TOLERANCE_PA = 25  # how far below setpoint counts as "too low"
MAX_GAP_SECONDS = 3600  # a silence longer than 1 hour is "unknown", not "still faulty"
CONFIRM_SECONDS = 600  # a fault must last 10 minutes (Day 14's two 5-minute rows)

# 1. Read the synthetic data and keep the first 4,000 rows (about 14 days) of each AHU
df = pd.read_csv("var/synthetic_ahu.csv")
df["row"] = (df["ts"] - START_TS) // 300  # 0, 1, 2, ... one number per 5-minute row
df = df[df["row"] < 4000]

# 2. Punch holes, the way a flaky network does: drop every 37th row (a 10-minute gap),
#    and drop 100 rows of AHU_1 in a row (an outage of about 8 hours)
dropped = df["row"] % 37 == 5
outage = (df["equipment_id"] == "AHU_1") & (df["row"] >= 400) & (df["row"] < 500)
df = df[~dropped & ~outage].copy()

# 3. Raw fault, the same as Day 14: fan on AND static more than 25 Pa below setpoint
fan_on = df["fan_status"] == 1
too_low = df["static_pa"] < df["setpoint_pa"] - TOLERANCE_PA
df["raw_fault"] = fan_on & too_low

# 4. Sample-and-hold: each reading holds until the next one arrives (per AHU).
#    A gap longer than the limit holds 0 seconds: we don't know what happened in it.
df["next_ts"] = df.groupby("equipment_id")["ts"].shift(-1)  # empty on each AHU's last row
df["seconds_to_next"] = df["next_ts"] - df["ts"]
df["gap_after"] = df["seconds_to_next"] > MAX_GAP_SECONDS
df["held_seconds"] = df["seconds_to_next"].where(~df["gap_after"], 0).fillna(0)

# 5. Streaks (Day 13): a new one starts when raw_fault changes, after a long gap,
#    or at the first row of the next AHU
changed = df["raw_fault"] != df["raw_fault"].shift()
after_gap = df["gap_after"].shift(fill_value=False)
new_ahu = df["equipment_id"] != df["equipment_id"].shift()
df["streak_id"] = (changed | after_gap | new_ahu).cumsum()

# 6. Confirm by elapsed time, not by counting rows: add up the held seconds inside each streak
df["streak_seconds"] = df.groupby("streak_id")["held_seconds"].cumsum()
df["fault"] = df["raw_fault"] & (df["streak_seconds"] >= CONFIRM_SECONDS)

# 7. Per AHU: fault hours, covered hours (time we can vouch for) and coverage
df["fault_seconds"] = df["held_seconds"].where(df["fault"], 0)
summary = df.groupby("equipment_id").agg(
    rows=("ts", "size"),
    long_gaps=("gap_after", "sum"),
    fault_seconds=("fault_seconds", "sum"),
    covered_seconds=("held_seconds", "sum"),
    first_ts=("ts", "min"),
    last_ts=("ts", "max"),
)
summary["fault_hours"] = summary["fault_seconds"] / 3600
summary["covered_hours"] = summary["covered_seconds"] / 3600
summary["window_hours"] = (summary["last_ts"] - summary["first_ts"]) / 3600
summary["coverage"] = summary["covered_hours"] / summary["window_hours"]
summary = summary[["rows", "long_gaps", "fault_hours", "covered_hours", "window_hours", "coverage"]]
summary = summary.reset_index()

# 8. The wrong way, for comparison: Day 14's rule (count rows x 5 minutes, ignore the gaps)
naive_streak_id = (changed | new_ahu).cumsum()
row_in_streak = df.groupby(naive_streak_id).cumcount() + 1
df["naive_fault"] = df["raw_fault"] & (row_in_streak >= 2)
naive = df.groupby("equipment_id")["naive_fault"].sum() * 5 / 60
naive = naive.reset_index(name="naive_fault_hours")

print("Rows left after the holes:", len(df), "of 8000")
print("\nGap-aware FC1 per AHU:")
print(summary.round(3).to_string(index=False))
print("\nRow counting (Day 14) on the same rows:")
print(naive.round(2).to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"summary": summary, "naive_fault_hours": naive}
