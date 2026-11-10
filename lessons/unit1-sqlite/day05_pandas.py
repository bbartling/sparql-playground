# Day 5 (pandas): group by month and by day.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day05_pandas.py

import pandas as pd

# 1. Read the columns we need
columns = ["timestamp_utc", "outside_air_temp_f", "supply_fan_status", "da_p_inwc"]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Make a month label ("2026-03") and a day label ("2026-03-16") from the timestamp
time = pd.to_datetime(df["timestamp_utc"], utc=True)
df["month"] = time.dt.strftime("%Y-%m")
df["day"] = time.dt.strftime("%Y-%m-%d")

# 3. The Week 1 challenge, one row per month: average temperature, fan run hours, high static
df["fan_hours"] = df["supply_fan_status"] * 5 / 60
df["static_high"] = df["da_p_inwc"] > 1.5
monthly = df.groupby("month").agg(
    avg_oat_f=("outside_air_temp_f", "mean"),
    fan_run_hours=("fan_hours", "sum"),
    static_above_1_5=("static_high", "sum"),
)
monthly = monthly.reset_index()
print(monthly.round(1).to_string(index=False))

# 4. The hottest day on average
daily_average = df.groupby("day")["outside_air_temp_f"].mean()
hottest_day = daily_average.idxmax()
hottest_avg = daily_average.max()
print("Hottest day:", hottest_day, "average (F):", round(hottest_avg, 2))

# 5. Days with fewer than 288 readings (24 hours x 12 per hour)
per_day = df.groupby("day").size().reset_index(name="n")
short_days = per_day[per_day["n"] < 288]
print(short_days.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "monthly": monthly,
    "hottest_day": hottest_day,
    "hottest_avg": hottest_avg,
    "short_days": short_days,
}
