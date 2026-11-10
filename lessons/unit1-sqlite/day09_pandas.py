# Day 9 (pandas): hourly and daily averages of AHU_1's outside air temperature.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day09_pandas.py

import pandas as pd

# 1. Read AHU_1's timestamps and outside air temperature
columns = ["timestamp_utc", "outside_air_temp_f"]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Convert to degC, and turn the timestamp text into real timestamps
df["outside_air_temp_c"] = (df["outside_air_temp_f"] - 32) * 5 / 9
df["time"] = pd.to_datetime(df["timestamp_utc"])

# 3. Give every row a bucket: the hour it is in, and the day it is in (as text)
df["hour"] = df["time"].dt.strftime("%Y-%m-%d %H")
df["day"] = df["time"].dt.strftime("%Y-%m-%d")

# 4. Average each bucket (rows = how many 5-minute rows fell in it)
hourly = df.groupby("hour").agg(rows=("time", "size"), mean_oa_c=("outside_air_temp_c", "mean"))
daily = df.groupby("day").agg(rows=("time", "size"), mean_oa_c=("outside_air_temp_c", "mean"))
hourly = hourly.reset_index()
daily = daily.reset_index()

# 5. The hottest day
hottest = daily.sort_values("mean_oa_c").iloc[-1]

print("Hourly rows:", len(hourly))
print("Daily rows: ", len(daily))
print("First hour:", hourly["hour"][0], "has only", hourly["rows"][0], "rows (a partial hour)")
print("Hottest day:", hottest["day"], "at", round(hottest["mean_oa_c"], 1), "C")

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"hourly": hourly, "daily": daily}
