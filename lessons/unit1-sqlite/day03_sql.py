# Day 3 (SQL): timestamps and a date range.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day03_sql.py

import sqlite3

conn = sqlite3.connect("var/lessons.sqlite")

# 1-2. The table is ahu_1. timestamp_utc is ISO text ("2026-03-16 00:40:00+00:00"),
#      and text in this format sorts in time order, so no conversion is needed

# 3. First and last reading
first_sql = "SELECT MIN(timestamp_utc), MAX(timestamp_utc) FROM ahu_1"
first_utc, last_utc = conn.execute(first_sql).fetchone()
print("First reading:", first_utc)
print("Last reading: ", last_utc)

# 4. Count the readings in a date range: start is included, end is not (one whole day)
range_sql = """
SELECT COUNT(*) FROM ahu_1
WHERE timestamp_utc >= :start AND timestamp_utc < :end
"""
july = {"start": "2026-07-01 00:00:00+00:00", "end": "2026-07-02 00:00:00+00:00"}
july_1 = conn.execute(range_sql, july).fetchone()[0]
print("Readings on 2026-07-01:", july_1, "(24 hours x 12 per hour)")

# 5. The first day is short: the data starts at 00:40, not midnight
march = {"start": "2026-03-16 00:00:00+00:00", "end": "2026-03-17 00:00:00+00:00"}
march_16 = conn.execute(range_sql, march).fetchone()[0]
print("Readings on 2026-03-16:", march_16)

# 6. Any gaps? unixepoch() turns the time text into seconds since 1970
gap_sql = """
SELECT (unixepoch(MAX(timestamp_utc)) - unixepoch(MIN(timestamp_utc))) / 300 + 1, COUNT(*)
FROM ahu_1
"""
expected_rows, actual_rows = conn.execute(gap_sql).fetchone()
print("Rows if every 5-minute step is there:", expected_rows)
print("Rows actually there:                 ", actual_rows)

# 7. The weekday of the first reading. strftime('%w') counts Sunday = 0 and returns text
weekday_sql = "SELECT CAST(strftime('%w', MIN(timestamp_utc)) AS INTEGER) FROM ahu_1"
first_weekday = conn.execute(weekday_sql).fetchone()[0]
print("Weekday of the first reading (0 = Sunday):", first_weekday)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "first_utc": first_utc,
    "last_utc": last_utc,
    "july_1": july_1,
    "march_16": march_16,
    "expected_rows": expected_rows,
    "actual_rows": actual_rows,
    "first_weekday": first_weekday,
}
