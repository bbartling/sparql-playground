# Day 17 (pandas): how much memory the same 100,000 rows cost as a list, a stream and a DataFrame.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day17_pandas.py

import tracemalloc

import pandas as pd

N = 100_000  # rows of AHU_1
TOLERANCE_PA = 25
HOURS_PER_ROW = 5 / 60
columns = ["fan_status", "static_pa", "setpoint_pa"]

# tracemalloc.start() ... get_traced_memory() measures the peak Python memory in between.

# 1. A list of tuples: every row alive in memory at once
df = pd.read_csv("var/synthetic_ahu.csv", nrows=N, usecols=columns)
tracemalloc.start()
rows = list(df.itertuples(index=False, name=None))
fault_rows = 0
for fan, static, setpoint in rows:
    if fan == 1 and static < setpoint - TOLERANCE_PA:
        fault_rows = fault_rows + 1
peak_list = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
del rows

# 2. A stream: one row at a time, nothing kept
tracemalloc.start()
fault_rows = 0
for fan, static, setpoint in df.itertuples(index=False, name=None):
    if fan == 1 and static < setpoint - TOLERANCE_PA:
        fault_rows = fault_rows + 1
peak_stream = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()

# 3. The whole file as a DataFrame (read it, then use whole-column math)
tracemalloc.start()
whole = pd.read_csv("var/synthetic_ahu.csv", nrows=N, usecols=columns)
fan_on = whole["fan_status"] == 1
too_low = whole["static_pa"] < whole["setpoint_pa"] - TOLERANCE_PA
fault_rows = (fan_on & too_low).sum()
peak_whole = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()

# 4. In chunks: read 10,000 rows at a time and add up the pieces
tracemalloc.start()
fault_rows = 0
run_rows = 0
for chunk in pd.read_csv("var/synthetic_ahu.csv", nrows=N, usecols=columns, chunksize=10_000):
    chunk_fan_on = chunk["fan_status"] == 1
    chunk_too_low = chunk["static_pa"] < chunk["setpoint_pa"] - TOLERANCE_PA
    fault_rows = fault_rows + (chunk_fan_on & chunk_too_low).sum()
    run_rows = run_rows + chunk_fan_on.sum()
peak_chunked = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
run_hours = run_rows * HOURS_PER_ROW

# 5. A smaller DataFrame: store the 0/1 flag as int8 and the floats as float32
small = whole.astype({"fan_status": "int8", "static_pa": "float32", "setpoint_pa": "float32"})

print("AHU_1, first", N, "rows")
print("  fault rows:", fault_rows)
print("  run hours: ", round(run_hours, 1))
print("Peak Python memory (MiB)")
print("  list of tuples:", round(peak_list / 2**20, 2))
print("  stream:        ", round(peak_stream / 2**20, 2))
print("  whole DataFrame:", round(peak_whole / 2**20, 2))
print("  chunked read:  ", round(peak_chunked / 2**20, 2))
print(
    "DataFrame size (MiB): default dtypes",
    round(whole.memory_usage().sum() / 2**20, 2),
    "-> smaller dtypes",
    round(small.memory_usage().sum() / 2**20, 2),
)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fault_rows": fault_rows, "run_hours": run_hours}
