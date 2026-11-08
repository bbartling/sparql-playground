"""Day 5, pandas: groupby per day and per month, filtering groups, and the Week 1 challenge.

    uv run python lessons/unit1-sqlite/day05_pandas.py

groupby splits rows into groups and an aggregate runs once per group. SQL's WHERE is a mask before
the groupby; SQL's HAVING is an ordinary filter on the small table groupby gives back.
Compare the printout with day05_sql.py: the numbers should match.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"
FULL_DAY = 288  # 24 h x 12 readings an hour

# 1. Load both AHUs, the columns we group. day and month are the text of the timestamp's date parts.
COLUMNS = ["timestamp_utc", "outside_air_temp_f", "da_p_inwc", "supply_fan_status"]
frames = []
for equip in ("AHU_1", "AHU_2"):
    f = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    f.insert(0, "equipment_id", equip)
    frames.append(f)
h = pd.concat(frames, ignore_index=True)
time = pd.to_datetime(h["timestamp_utc"], utc=True)
h["day"] = time.dt.strftime("%Y-%m-%d")
h["month"] = time.dt.strftime("%Y-%m")
ahu_1 = h[h["equipment_id"] == "AHU_1"]

# 2. Monthly average outside air temperature: groupby a column, agg for the statistic.
monthly_avg = ahu_1.groupby("month").agg(avg_f=("outside_air_temp_f", "mean")).reset_index()

# 3. Readings per day, then the hottest day on average (sort the small result, keep the top row).
daily_counts = ahu_1.groupby("day").agg(n=("outside_air_temp_f", "size")).reset_index()
daily_avg = ahu_1.groupby("day").agg(avg_f=("outside_air_temp_f", "mean")).reset_index()
hottest_day = daily_avg.sort_values("avg_f", ascending=False).head(1).reset_index(drop=True)

# 4. HAVING: days without a full 288 readings. A filter AFTER the groupby.
short_days = daily_counts[daily_counts["n"] < FULL_DAY].reset_index(drop=True)

# 5. WHERE before GROUP BY: readings above 90 F per day. Days with none have no rows to group.
hot_counts = (
    ahu_1[ahu_1["outside_air_temp_f"] > 90]
    .groupby("day")
    .agg(n_hot=("outside_air_temp_f", "size"))
    .reset_index()
)

# 6. Daily fan run hours; the three longest days, and how many days ran all 24 hours.
daily_hours = (
    ahu_1.groupby("day")
    .agg(run_hours=("supply_fan_status", lambda s: s.sum() * 5 / 60))
    .reset_index()
)
longest_days = (
    daily_hours.sort_values(["run_hours", "day"], ascending=[False, True])
    .head(3)
    .reset_index(drop=True)
)
full_run_days = daily_hours[daily_hours["run_hours"] >= 24].reset_index(drop=True)

# 7. Week 1 challenge: per AHU and month, the average outside air temperature, the fan run hours,
# and the number of readings with duct static above 1.5 inH2O. One groupby on two keys.
h["static_high"] = h["da_p_inwc"] > 1.5
challenge = (
    h.groupby(["equipment_id", "month"])
    .agg(
        avg_oat_f=("outside_air_temp_f", "mean"),
        fan_run_hours=("supply_fan_status", lambda s: s.sum() * 5 / 60),
        static_above_1_5=("static_high", "sum"),
    )
    .reset_index()
)
challenge["static_above_1_5"] = challenge["static_above_1_5"].astype(int)

RESULTS = {
    "monthly_avg": monthly_avg,
    "daily_counts": daily_counts,
    "hottest_day": hottest_day,
    "short_days": short_days,
    "hot_counts": hot_counts,
    "longest_days": longest_days,
    "full_run_days": full_run_days,
    "challenge": challenge,
}

print("AHU_1 monthly average outside air temperature (F):")
print(monthly_avg.round(1).to_string(index=False))
print("\nthe hottest day on average:")
print(hottest_day.round(2).to_string(index=False))
print("\ndays with fewer than 288 readings:")
print(short_days.to_string(index=False))
print(f"\ndays that ever passed 90 F: {len(hot_counts)} of {len(daily_counts)}")
print("\nthe three longest fan run days (hours):")
print(longest_days.round(1).to_string(index=False))
print(f"days the fan ran all 24 hours: {len(full_run_days)} of {len(daily_hours)}")
print("\nWeek 1 challenge, per AHU and month:")
print(challenge.round({"avg_oat_f": 1, "fan_run_hours": 1}).to_string(index=False))
