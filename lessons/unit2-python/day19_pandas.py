# Day 19 (pandas): the as-of join. Give every AHU row the latest weather reading, if it is recent.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day19_pandas.py

import time
from bisect import bisect_right

import pandas as pd

MAX_AGE_SECONDS = 2 * 3600  # weather older than 2 hours is "stale": unknown, not used
DIFF_C = 3  # the sensor and the weather may differ by up to 3 C
CONFIRM_ROWS = 6  # 6 rows x 5 min = 30 minutes

# 1. Read AHU_1's first 100,000 rows (every 5 minutes) and the hourly weather (some hours missing).
#    Both use ts = epoch seconds.
ahu = pd.read_csv("var/synthetic_ahu.csv", nrows=100_000)
weather = pd.read_csv("var/synthetic_weather.csv")
weather = weather.rename(columns={"ts": "weather_ts", "temp_c": "weather_c"})

# 2. The as-of join: for each AHU row, the latest weather row at or before it ("backward"),
#    but no older than MAX_AGE_SECONDS. Both tables must be sorted by time (they are).
start = time.perf_counter()
joined = pd.merge_asof(
    ahu,
    weather,
    left_on="ts",
    right_on="weather_ts",
    direction="backward",
    tolerance=MAX_AGE_SECONDS,
)
asof_seconds = time.perf_counter() - start
rows_without_weather = joined["weather_c"].isna().sum()
average_weather_c = joined["weather_c"].mean()

# 3. The same lookup in plain Python: binary search (bisect) in the sorted list of weather times
weather_times = weather["weather_ts"].tolist()
start = time.perf_counter()
matched = 0
for ts in ahu["ts"]:
    i = bisect_right(weather_times, ts) - 1  # position of the last weather time <= ts
    if i >= 0 and ts - weather_times[i] <= MAX_AGE_SECONDS:
        matched = matched + 1
bisect_seconds = time.perf_counter() - start

# 4. And the slow way, on the first 200 rows only: check every weather row for every AHU row
start = time.perf_counter()
for ts in ahu["ts"][:200]:
    latest = None
    for weather_ts in weather_times:
        if weather_ts <= ts:
            latest = weather_ts
nested_seconds = time.perf_counter() - start

# 5. A sensor-versus-weather rule: the fan is on and the AHU's outdoor sensor is more than
#    3 C away from the weather, for 6 rows in a row. No weather means no fault (unknown).
fan_on = joined["fan_status"] == 1
far_apart = (joined["oat_c"] - joined["weather_c"]).abs() > DIFF_C
joined["raw_fault"] = fan_on & far_apart
joined["new_streak"] = joined["raw_fault"] != joined["raw_fault"].shift()
joined["streak_id"] = joined["new_streak"].cumsum()
joined["row_in_streak"] = joined.groupby("streak_id").cumcount() + 1
joined["fault"] = joined["raw_fault"] & (joined["row_in_streak"] >= CONFIRM_ROWS)
raw_rows = joined["raw_fault"].sum()
fault_rows = joined["fault"].sum()
fault_hours = fault_rows * 5 / 60

print("AHU rows:", len(ahu), "| weather rows:", len(weather))
print("Rows with no usable weather:", rows_without_weather)
print("Average weather temperature on the matched rows (C):", round(average_weather_c, 3))
print("bisect loop matched the same rows:", matched == len(ahu) - rows_without_weather)
print("\nSensor vs weather rule (fan on, more than 3 C apart for 30 minutes):")
print("  raw rows:", raw_rows, "| confirmed rows:", fault_rows, "| hours:", round(fault_hours, 2))
print("\nMicroseconds per AHU row (times vary by machine):")
print("  nested loop:", round(nested_seconds / 200 * 1_000_000, 2))
print("  bisect loop:", round(bisect_seconds / len(ahu) * 1_000_000, 2))
print("  merge_asof: ", round(asof_seconds / len(ahu) * 1_000_000, 2))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "rows_without_weather": rows_without_weather,
    "average_weather_c": average_weather_c,
    "raw_rows": raw_rows,
    "fault_rows": fault_rows,
    "fault_hours": fault_hours,
}
