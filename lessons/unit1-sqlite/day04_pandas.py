# Day 4 (pandas): average, min and max of a column, and fan run hours.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day04_pandas.py

import pandas as pd

# 1. Read the two columns we need
columns = ["outside_air_temp_f", "supply_fan_status"]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Average, minimum and maximum outside air temperature
average_f = df["outside_air_temp_f"].mean()
min_f = df["outside_air_temp_f"].min()
max_f = df["outside_air_temp_f"].max()
print("Outside air temperature (F): average", round(average_f, 2), "min", min_f, "max", max_f)

# 3. Run hours: fan status is 1 when running, 0 when off, one reading every 5 minutes
fan_readings_on = df["supply_fan_status"].sum()
run_hours = fan_readings_on * 5 / 60
print("Supply fan run hours:", round(run_hours, 1))

# 4. The average of a 0/1 column is the fraction of time it was 1
fraction_running = df["supply_fan_status"].mean()
print("Fraction of time the fan ran:", round(fraction_running, 3))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "average_f": average_f,
    "min_f": min_f,
    "max_f": max_f,
    "run_hours": run_hours,
    "fraction_running": fraction_running,
}
