# Day 11 (pandas): one week of rows, found by scanning a column vs by looking up a sorted index.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day11_pandas.py

import time

import pandas as pd

# The week we want: from May 1 up to (not including) May 8
start = "2026-05-01 00:00:00+00:00"
end = "2026-05-08 00:00:00+00:00"
last_row = "2026-05-07 23:55:00+00:00"  # .loc includes its end label, so name the last row

# 1. Read AHU_1's data, only the columns we need
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=["timestamp_utc", "da_p_inwc"])

# 2. Scan: compare every row's timestamp with the start and end
t0 = time.perf_counter()
in_week = (df["timestamp_utc"] >= start) & (df["timestamp_utc"] < end)
week = df[in_week]
scan_ms = (time.perf_counter() - t0) * 1000

# 3. Index: sort by timestamp once, then .loc jumps straight to the week
t0 = time.perf_counter()
indexed = df.set_index("timestamp_utc").sort_index()
build_ms = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
week_indexed = indexed.loc[start:last_row]
lookup_ms = (time.perf_counter() - t0) * 1000

# 4. A rare value in a column we did not index: this can only be a scan
high = df[df["da_p_inwc"] > 1.7]

print("Rows in the week:", len(week))
print("Rows in the week (index lookup):", len(week_indexed))
print("Average duct static in the week (inH2O):", round(week["da_p_inwc"].mean(), 4))
print("Rows with duct static above 1.7 inH2O:", len(high))
print("Scan time (ms):", round(scan_ms, 3))
print("Index lookup time (ms):", round(lookup_ms, 3))
print("Time to build the index once (ms):", round(build_ms, 3))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "week_rows": len(week),
    "week_rows_indexed": len(week_indexed),
    "week_avg_static_inwc": week["da_p_inwc"].mean(),
    "high_static_rows": len(high),
}
