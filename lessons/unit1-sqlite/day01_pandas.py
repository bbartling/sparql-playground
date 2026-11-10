# Day 1 (pandas): open AHU_1's CSV and look at its shape, columns and first rows.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day01_pandas.py

import pandas as pd

# 1. Read the CSV file into a table (a "DataFrame")
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv")

# 2. Shape: how many rows and columns?
rows, columns = df.shape
print("Rows:", rows)
print("Columns:", columns)

# 3. The first five column names
column_names = list(df.columns[:5])
print("First column names:", column_names)

# 4. The first five rows of a few columns
show = ["timestamp_utc", "outside_air_temp_f", "da_p_inwc", "da_p_setpoint_inwc"]
first_rows = df[show].head(5)
print(first_rows.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"rows": rows, "columns": columns, "first_rows": first_rows}
