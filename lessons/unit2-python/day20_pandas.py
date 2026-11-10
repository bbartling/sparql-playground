# Day 20 (pandas): Day 14's FC1 rule as a plain Python loop and as pandas, on growing data.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day20_pandas.py

import time

import pandas as pd

START_TS = 1_773_619_200  # the synthetic data's first timestamp (epoch seconds)
TOLERANCE_PA = 25  # how far below setpoint counts as "too low"
CONFIRM_ROWS = 2  # the fault must last 2 rows in a row

# 1. Read the synthetic data: two AHUs, 500,000 rows each
everything = pd.read_csv("var/synthetic_ahu.csv")
ahu_1 = everything[everything["equipment_id"] == "AHU_1"]

# 2. The showdown: the same rule two ways, on 1,000 to 500,000 rows of AHU_1
sizes = []
for n in [1_000, 10_000, 100_000, 500_000]:
    df = ahu_1.head(n)
    fan = df["fan_status"].tolist()
    static = df["static_pa"].tolist()
    setpoint = df["setpoint_pa"].tolist()

    # 2a. The loop: a tiny "state machine". streak_length is all it remembers between rows.
    start = time.perf_counter()
    previous_raw = None
    streak_length = 0
    loop_fault_rows = 0
    loop_episodes = 0
    for i in range(n):
        raw = fan[i] == 1 and static[i] < setpoint[i] - TOLERANCE_PA
        streak_length = streak_length + 1
        if raw != previous_raw:
            streak_length = 1  # the value changed: a new streak starts here
        previous_raw = raw
        if raw and streak_length >= CONFIRM_ROWS:
            loop_fault_rows = loop_fault_rows + 1
        if raw and streak_length == CONFIRM_ROWS:
            loop_episodes = loop_episodes + 1  # the row where a streak becomes confirmed
    loop_seconds = time.perf_counter() - start

    # 2b. pandas: Day 14's column trick (number the streaks, count rows inside each)
    start = time.perf_counter()
    raw = (df["fan_status"] == 1) & (df["static_pa"] < df["setpoint_pa"] - TOLERANCE_PA)
    streak_id = (raw != raw.shift()).cumsum()
    row_in_streak = raw.groupby(streak_id).cumcount() + 1
    fault_rows = (raw & (row_in_streak >= CONFIRM_ROWS)).sum()
    episodes = (raw & (row_in_streak == CONFIRM_ROWS)).sum()
    pandas_seconds = time.perf_counter() - start

    print("rows:", n, "| fault rows:", fault_rows, "| episodes:", episodes)
    print("  loop agrees:", loop_fault_rows == fault_rows and loop_episodes == episodes)
    print("  seconds: loop", round(loop_seconds, 4), "| pandas", round(pandas_seconds, 4))
    sizes.append({"rows": n, "fault_rows": fault_rows, "episodes": episodes})
totals_by_size = pd.DataFrame(sizes)

# 3. Stop early: the first confirmed fault in AHU_1's first 200,000 rows
df = ahu_1.head(200_000)
fan = df["fan_status"].tolist()
static = df["static_pa"].tolist()
setpoint = df["setpoint_pa"].tolist()
times = df["ts"].tolist()

start = time.perf_counter()
previous_raw = None
streak_length = 0
first_fault_ts = None
for i in range(len(times)):
    raw = fan[i] == 1 and static[i] < setpoint[i] - TOLERANCE_PA
    streak_length = streak_length + 1
    if raw != previous_raw:
        streak_length = 1  # the value changed: a new streak starts here
    previous_raw = raw
    if raw and streak_length >= CONFIRM_ROWS:
        first_fault_ts = times[i]
        break  # found it: the rest of the table is never read
early_seconds = time.perf_counter() - start

start = time.perf_counter()
raw = (df["fan_status"] == 1) & (df["static_pa"] < df["setpoint_pa"] - TOLERANCE_PA)
streak_id = (raw != raw.shift()).cumsum()
row_in_streak = raw.groupby(streak_id).cumcount() + 1
fault = raw & (row_in_streak >= CONFIRM_ROWS)
pandas_first_ts = df[fault]["ts"].min()
pandas_first_seconds = time.perf_counter() - start

print("\nFirst confirmed fault in 200,000 rows: ts", first_fault_ts)
print("  pandas finds the same one:", pandas_first_ts == first_fault_ts)
print("  seconds: loop with early exit", round(early_seconds, 4))
print("  seconds: pandas (computes every row first)", round(pandas_first_seconds, 4))

# 4. Week 4 challenge: the longest confirmed episode per AHU, in the first 20,000 rows of each
longest_rows = []
for ahu in ["AHU_1", "AHU_2"]:
    df = everything[everything["equipment_id"] == ahu]
    df = df[df["ts"] < START_TS + 20_000 * 300]
    raw = (df["fan_status"] == 1) & (df["static_pa"] < df["setpoint_pa"] - TOLERANCE_PA)
    streaks = pd.DataFrame({"raw": raw, "streak_id": (raw != raw.shift()).cumsum()})
    streak_sizes = streaks.groupby("streak_id").agg(raw=("raw", "first"), rows=("raw", "size"))
    faults = streak_sizes[streak_sizes["raw"] & (streak_sizes["rows"] >= CONFIRM_ROWS)]
    longest = faults["rows"].max()
    longest_rows.append({"equipment_id": ahu, "longest_rows": longest, "longest_min": longest * 5})
longest_episode = pd.DataFrame(longest_rows)

print("\nLongest confirmed episode per AHU (20,000 rows each):")
print(longest_episode.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "totals_by_size": totals_by_size,
    "first_fault_ts": first_fault_ts,
    "longest_episode": longest_episode,
}
