# Day 3 (pandas): timestamps and a date range.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day03_pandas.py

import pandas as pd

# 1. Read the timestamp column
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=["timestamp_utc"])

# 2. Turn the text into real timestamps (utc=True says they are UTC)
df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True)

# 3. First and last reading
first_utc = str(df["time"].min())
last_utc = str(df["time"].max())
print("First reading:", first_utc)
print("Last reading: ", last_utc)

# 4. Count the readings in a date range: start is included, end is not (one whole day)
start = pd.Timestamp("2026-07-01", tz="UTC")
end = pd.Timestamp("2026-07-02", tz="UTC")
in_range = df[(df["time"] >= start) & (df["time"] < end)]
print("Readings on 2026-07-01:", len(in_range), "(24 hours x 12 per hour)")

# 5. The first day is short: the data starts at 00:40, not midnight
start = pd.Timestamp("2026-03-16", tz="UTC")
end = pd.Timestamp("2026-03-17", tz="UTC")
first_day = df[(df["time"] >= start) & (df["time"] < end)]
print("Readings on 2026-03-16:", len(first_day))

# 6. Any gaps? From the first to the last reading, every 5-minute step should be there
span_seconds = (df["time"].max() - df["time"].min()).total_seconds()
expected_rows = int(span_seconds / 300) + 1
print("Rows if every 5-minute step is there:", expected_rows)
print("Rows actually there:                 ", len(df))

# 7. The weekday of the first reading. pandas counts Monday = 0; SQL counts Sunday = 0,
#    so convert to SQL's way before comparing
first_weekday = (df["time"].min().dayofweek + 1) % 7
print("Weekday of the first reading (0 = Sunday):", first_weekday)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "first_utc": first_utc,
    "last_utc": last_utc,
    "july_1": len(in_range),
    "march_16": len(first_day),
    "expected_rows": expected_rows,
    "actual_rows": len(df),
    "first_weekday": first_weekday,
}
