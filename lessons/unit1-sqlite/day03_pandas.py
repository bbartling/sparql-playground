"""Day 3, pandas: time. ISO text timestamps, date parts, half-open ranges, local time.

    uv run python lessons/unit1-sqlite/day03_pandas.py

The CSV's timestamp_utc is text like '2026-03-16 00:40:00+00:00'. pd.to_datetime turns it into a
real time-zone-aware datetime column with the whole .dt toolbox.
Compare the printout with day03_sql.py: the numbers should match.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"
FMT = "%Y-%m-%d %H:%M:%S"
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")

# 1. Load, then parse the text into datetime64[ns, UTC]. utc=True keeps every value time-zone aware.
COLUMNS = ["timestamp_utc", "outside_air_temp_f", "supply_fan_status"]
df = pd.read_csv(DATA / "AHU_1" / "history_wide.csv", usecols=COLUMNS)
df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True)

# 2. The first three readings as dates and as Unix epoch seconds (seconds since 1970-01-01 UTC).
first3 = df.sort_values("time").head(3)
first3 = pd.DataFrame(
    {
        "time_utc": first3["time"].dt.strftime(FMT),
        "epoch_s": (first3["time"] - EPOCH).dt.total_seconds().astype(int),
        "outside_air_temp_f": first3["outside_air_temp_f"],
    }
).reset_index(drop=True)

# 3. First and last timestamp, and a gap check: 5-minute steps from first to last need N rows.
first, last = df["time"].min(), df["time"].max()
span = pd.DataFrame({"first_utc": [first.strftime(FMT)], "last_utc": [last.strftime(FMT)]})
span_s = int((last - first).total_seconds())
gap_check = pd.DataFrame(
    {"span_s": [span_s], "expected_rows": [span_s // 300 + 1], "actual_rows": [len(df)]}
)

# 4. A day, as a HALF-OPEN range: start <= time < end, so consecutive days never share a reading.
DAY, NEXT_DAY = pd.Timestamp("2026-07-01", tz="UTC"), pd.Timestamp("2026-07-02", tz="UTC")
july_1 = pd.DataFrame({"n": [int(((df["time"] >= DAY) & (df["time"] < NEXT_DAY)).sum())]})
FIRST_DAY, SECOND_DAY = pd.Timestamp("2026-03-16", tz="UTC"), pd.Timestamp("2026-03-17", tz="UTC")
first_day = pd.DataFrame(
    {"n": [int(((df["time"] >= FIRST_DAY) & (df["time"] < SECOND_DAY)).sum())]}
)

# 5. The same day by computing a date for every row: same rows, but O(n) work every time.
july_1_by_date = pd.DataFrame(
    {"n": [int((df["time"].dt.strftime("%Y-%m-%d") == "2026-07-01").sum())]}
)

# 6. A closed range on text that is too short misses the whole day (the text has a time on it).
sloppy = pd.DataFrame(
    {
        "n": [
            int(
                (
                    (df["timestamp_utc"] >= "2026-07-01") & (df["timestamp_utc"] <= "2026-07-01")
                ).sum()
            )
        ]
    }
)

# 7. Weekday: pandas counts Monday = 0, SQLite's %w counts Sunday = 0. Convert to compare.
first_weekday = (first.dayofweek + 1) % 7  # 2026-03-16 is a Monday: 0 in pandas, 1 in SQL
weekday = pd.DataFrame(
    {
        "first_weekday_sun0": [first_weekday],
        "weekday_rows": [int((df["time"].dt.dayofweek < 5).sum())],  # Mon..Fri, UTC calendar
    }
)

# 8. When did the fan first start on 2026-04-01? (UTC; local time below.)
on = df[(df["supply_fan_status"] == 1) & (df["time"] >= "2026-04-01") & (df["time"] < "2026-04-02")]
fan_start = pd.DataFrame({"fan_start_utc": [on["time"].min().strftime(FMT)]})

# 9. The hottest reading, in UTC.
hot = df.loc[[df["outside_air_temp_f"].idxmax()]]
hottest = pd.DataFrame(
    {"time_utc": hot["time"].dt.strftime(FMT), "outside_air_temp_f": hot["outside_air_temp_f"]}
).reset_index(drop=True)

RESULTS = {
    "first3": first3,
    "span": span,
    "gap_check": gap_check,
    "july_1": july_1,
    "first_day": first_day,
    "july_1_by_date": july_1_by_date,
    "sloppy": sloppy,
    "weekday": weekday,
    "fan_start": fan_start,
    "hottest": hottest,
}

print("dtype of the parsed column:", df["time"].dtype)
print("\nfirst three readings, as dates and epoch seconds:")
print(first3.to_string(index=False))
print("\nfirst and last timestamp:")
print(span.to_string(index=False))
print("rows if every 5-minute step is present:", gap_check["expected_rows"][0])
print("rows actually there:                   ", gap_check["actual_rows"][0])
print("\nreadings on 2026-07-01 (half-open range):", july_1["n"][0])
print("readings on 2026-03-16 (data starts at 00:40):", first_day["n"][0])
print("same day via a computed date on every row:", july_1_by_date["n"][0])
print(
    "BETWEEN '2026-07-01' AND '2026-07-01' on text:",
    sloppy["n"][0],
    "(the day's rows all sort after it)",
)
print("\nweekday of the first row (0 = Sunday, as SQL counts):", weekday["first_weekday_sun0"][0])
print("Monday-to-Friday readings (UTC calendar):", weekday["weekday_rows"][0])
print(
    "\nthe hottest reading, UTC:",
    hottest["time_utc"][0],
    round(hottest["outside_air_temp_f"][0], 2),
)

# Local time is a job for pandas: it knows named zones and daylight saving. SQLite does not.
CHICAGO = "America/Chicago"
print("  ... and in", CHICAGO, ":", hot["time"].iloc[0].tz_convert(CHICAGO))
start_local = on["time"].min().tz_convert(CHICAGO)
print(
    "fan first started on 2026-04-01 at",
    fan_start["fan_start_utc"][0],
    "UTC =",
    start_local,
    "local",
)

# Naive vs aware: pandas refuses to compare them. That error is the friendly outcome.
naive = pd.to_datetime(df["timestamp_utc"].str.slice(0, 19))  # drops the +00:00: no zone
try:
    _ = naive >= DAY
except TypeError as err:
    print("\nTypeError:", err)
