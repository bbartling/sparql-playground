"""Day 3, SQL: time. ISO text timestamps, datetime()/strftime()/unixepoch(), half-open ranges.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day03_sql.py

SQLite has no date type. timestamp_utc is TEXT like '2026-03-16 00:40:00+00:00', and the date
functions parse that text row by row. SQLite does all the work; pandas only turns the result rows
into a table for printing.
Compare the printout with day03_pandas.py: the numbers should match.
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)


def q(sql, params=None):
    """Run one SELECT with its parameters and return a DataFrame."""
    return pd.read_sql_query(sql, conn, params=params or {})


# 1. Nothing to parse up front: the column is text, and the functions below read it directly.
TYPEOF_SQL = "SELECT typeof(timestamp_utc) AS stored_as FROM ahu_1 LIMIT 1"

# 2. The first three readings as dates and as Unix epoch seconds (seconds since 1970-01-01 UTC).
FIRST3_SQL = """
SELECT datetime(timestamp_utc)   AS time_utc,
       unixepoch(timestamp_utc)  AS epoch_s,
       outside_air_temp_f
FROM ahu_1
ORDER BY timestamp_utc
LIMIT 3
"""

# 3. First and last timestamp, and a gap check: 5-minute steps from first to last need N rows.
SPAN_SQL = """
SELECT datetime(min(timestamp_utc)) AS first_utc, datetime(max(timestamp_utc)) AS last_utc
FROM ahu_1
"""
GAP_CHECK_SQL = """
SELECT unixepoch(max(timestamp_utc)) - unixepoch(min(timestamp_utc))        AS span_s,
       (unixepoch(max(timestamp_utc)) - unixepoch(min(timestamp_utc))) / 300 + 1 AS expected_rows,
       count(*)                                                              AS actual_rows
FROM ahu_1
"""

# 4. A day, as a HALF-OPEN range: start <= time < end, so consecutive days never share a reading.
# The bounds are text in the column's own format, so SQLite compares the raw column to them and can
# seek in the PRIMARY KEY index: O(log n + k).
DAY_SQL = """
SELECT count(*) AS n FROM ahu_1 WHERE timestamp_utc >= :start AND timestamp_utc < :end
"""

# 5. The same day by computing a date for every row: same rows, but SQLite can't use the index.
BY_DATE_SQL = "SELECT count(*) AS n FROM ahu_1 WHERE date(timestamp_utc) = :day"

# 6. A closed range on text that is too short misses the whole day (the text has a time on it).
SLOPPY_SQL = """
SELECT count(*) AS n FROM ahu_1 WHERE timestamp_utc BETWEEN :start AND :end
"""

# 7. Weekday: SQLite's %w counts Sunday = 0 and returns TEXT; pandas counts Monday = 0.
WEEKDAY_SQL = """
SELECT CAST(strftime('%w', min(timestamp_utc)) AS INTEGER) AS first_weekday_sun0,
       sum(CAST(strftime('%w', timestamp_utc) AS INTEGER) BETWEEN 1 AND 5) AS weekday_rows
FROM ahu_1
"""

# 8. When did the fan first start on 2026-04-01? (UTC; local time below.)
FAN_START_SQL = """
SELECT datetime(min(timestamp_utc)) AS fan_start_utc
FROM ahu_1
WHERE supply_fan_status = 1 AND timestamp_utc >= :start AND timestamp_utc < :end
"""

# 9. The hottest reading, in UTC.
HOTTEST_SQL = """
SELECT datetime(timestamp_utc) AS time_utc, outside_air_temp_f
FROM ahu_1
ORDER BY outside_air_temp_f DESC, timestamp_utc
LIMIT 1
"""

# Text in the same format as the column. pandas builds the same strings with str(Timestamp).
JULY_1 = {"start": "2026-07-01 00:00:00+00:00", "end": "2026-07-02 00:00:00+00:00"}
MARCH_16 = {"start": "2026-03-16 00:00:00+00:00", "end": "2026-03-17 00:00:00+00:00"}
APRIL_1 = {"start": "2026-04-01 00:00:00+00:00", "end": "2026-04-02 00:00:00+00:00"}

stored_as = q(TYPEOF_SQL)["stored_as"][0]
first3 = q(FIRST3_SQL)
span = q(SPAN_SQL)
gap_check = q(GAP_CHECK_SQL)
july_1 = q(DAY_SQL, JULY_1)
first_day = q(DAY_SQL, MARCH_16)
july_1_by_date = q(BY_DATE_SQL, {"day": "2026-07-01"})
sloppy = q(SLOPPY_SQL, {"start": "2026-07-01", "end": "2026-07-01"})
weekday = q(WEEKDAY_SQL)
fan_start = q(FAN_START_SQL, APRIL_1)
hottest = q(HOTTEST_SQL)

# Which plan did SQLite pick? SEARCH ... USING ... INDEX is a seek; SCAN reads every row.
plan_range = conn.execute("EXPLAIN QUERY PLAN " + DAY_SQL, JULY_1).fetchall()[0][-1]
plan_date = conn.execute("EXPLAIN QUERY PLAN " + BY_DATE_SQL, {"day": "2026-07-01"}).fetchall()[0][
    -1
]

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

print("timestamp_utc is stored as:", stored_as)
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
print("  plan, range  :", plan_range)
print("  plan, date() :", plan_date)
print("\nweekday of the first row (0 = Sunday, as SQL counts):", weekday["first_weekday_sun0"][0])
print("Monday-to-Friday readings (UTC calendar):", weekday["weekday_rows"][0])
print(
    "\nthe hottest reading, UTC:",
    hottest["time_utc"][0],
    round(hottest["outside_air_temp_f"][0], 2),
)

# SQLite has no named zones, only 'localtime': the zone of whatever machine runs the query.
local = conn.execute(
    "SELECT datetime(:ts, 'localtime')", {"ts": hottest["time_utc"][0]}
).fetchone()[0]
print("  ... 'localtime' on THIS machine:", local, "(changes with the machine's zone)")
print("fan first started on 2026-04-01 at", fan_start["fan_start_utc"][0], "UTC")
