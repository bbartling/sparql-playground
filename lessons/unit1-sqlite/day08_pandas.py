# Day 8 (pandas): conditional counts. Run hours, unoccupied runtime, percent occupied.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day08_pandas.py

import pandas as pd

PA_PER_INH2O = 249.08891  # 1 inch of water = 249.09 pascals

# 1. Read AHU_1's data, only the columns we need
columns = ["supply_fan_status", "occ_c", "da_p_inwc"]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)

# 2. Conditions: one True/False per row
fan_on = df["supply_fan_status"] == 1
occupied = df["occ_c"] == 1
fan_on_unoccupied = fan_on & ~occupied  # ~ means "not"

# 3. Count the rows where each condition is True (each row is 5 minutes, so rows x 5 / 60 = hours)
run_hours = fan_on.sum() * 5 / 60
unoccupied_run_hours = fan_on_unoccupied.sum() * 5 / 60
percent_occupied = occupied.mean() * 100  # the mean of True/False is the fraction of True
percent_run_unoccupied = 100 * unoccupied_run_hours / run_hours

# 4. Average duct static pressure, only on the rows where the fan runs
static_running_pa = df[fan_on]["da_p_inwc"].mean() * PA_PER_INH2O

print("Run hours:", round(run_hours, 2))
print("Run hours while unoccupied:", round(unoccupied_run_hours, 2))
print("Percent of rows occupied:", round(percent_occupied, 2))
print("Percent of run time unoccupied:", round(percent_run_unoccupied, 2))
print("Average static while the fan runs (Pa):", round(static_running_pa, 1))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "run_hours": run_hours,
    "unoccupied_run_hours": unoccupied_run_hours,
    "percent_occupied": percent_occupied,
    "percent_run_unoccupied": percent_run_unoccupied,
    "static_running_pa": static_running_pa,
}
