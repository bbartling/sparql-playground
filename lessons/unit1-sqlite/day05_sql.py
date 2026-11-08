"""Day 5, SQL: GROUP BY and HAVING per day and per month, and the Week 1 challenge.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day05_sql.py

GROUP BY splits rows into groups and each aggregate runs once per group. WHERE throws rows away
before they are grouped; HAVING throws whole groups away after, so it can use aggregates.
SQLite does all the work; pandas only turns the result rows into a table for printing.
Compare the printout with day05_pandas.py: the numbers should match.
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


# 1. Both AHUs, the columns we group, in a temp view. day and month are computed by SQLite's date
# functions from the timestamp text. (A view stores the query, not the rows.)
conn.execute("""
CREATE TEMP VIEW h AS
SELECT 'AHU_1' AS equipment_id, timestamp_utc, outside_air_temp_f, da_p_inwc, supply_fan_status,
       date(timestamp_utc) AS day, strftime('%Y-%m', timestamp_utc) AS month
FROM ahu_1
UNION ALL
SELECT 'AHU_2', timestamp_utc, outside_air_temp_f, da_p_inwc, supply_fan_status,
       date(timestamp_utc), strftime('%Y-%m', timestamp_utc)
FROM ahu_2
""")

# 2. Monthly average outside air temperature: GROUP BY an expression, aggregate per group.
MONTHLY_SQL = """
SELECT month, avg(outside_air_temp_f) AS avg_f
FROM h WHERE equipment_id = 'AHU_1'
GROUP BY month
ORDER BY month
"""

# 3. Readings per day, then the hottest day on average (sort the small result, keep the top row).
DAILY_COUNTS_SQL = """
SELECT day, count(*) AS n FROM h WHERE equipment_id = 'AHU_1' GROUP BY day ORDER BY day
"""
HOTTEST_DAY_SQL = """
SELECT day, avg(outside_air_temp_f) AS avg_f
FROM h WHERE equipment_id = 'AHU_1'
GROUP BY day
ORDER BY avg_f DESC
LIMIT 1
"""

# 4. HAVING: days without a full 288 readings. The condition is on count(*), so it can't be WHERE.
SHORT_DAYS_SQL = """
SELECT day, count(*) AS n
FROM h WHERE equipment_id = 'AHU_1'
GROUP BY day
HAVING count(*) < :full_day
ORDER BY day
"""

# 5. WHERE before GROUP BY: readings above 90 F per day. Days with none have no rows to group.
HOT_COUNTS_SQL = """
SELECT day, count(*) AS n_hot
FROM h
WHERE equipment_id = 'AHU_1' AND outside_air_temp_f > :hot_f   -- row filter, before grouping
GROUP BY day
ORDER BY day
"""

# 6. Daily fan run hours; the three longest days, and the days that ran all 24 hours.
LONGEST_DAYS_SQL = """
SELECT day, sum(supply_fan_status) * 5 / 60.0 AS run_hours
FROM h WHERE equipment_id = 'AHU_1'
GROUP BY day
ORDER BY run_hours DESC, day
LIMIT 3
"""
FULL_RUN_DAYS_SQL = """
SELECT day, sum(supply_fan_status) * 5 / 60.0 AS run_hours
FROM h WHERE equipment_id = 'AHU_1'
GROUP BY day
HAVING sum(supply_fan_status) * 5 / 60.0 >= 24
ORDER BY day
"""

# 7. Week 1 challenge: per AHU and month, the average outside air temperature, the fan run hours,
# and the number of readings with duct static above 1.5 inH2O. One query: a comparison is 0 or 1,
# so sum() counts the rows where it is true.
CHALLENGE_SQL = """
SELECT equipment_id, month,
       avg(outside_air_temp_f)           AS avg_oat_f,
       sum(supply_fan_status) * 5 / 60.0 AS fan_run_hours,
       sum(da_p_inwc > 1.5)              AS static_above_1_5
FROM h
GROUP BY equipment_id, month
ORDER BY equipment_id, month
"""

monthly_avg = q(MONTHLY_SQL)
daily_counts = q(DAILY_COUNTS_SQL)
hottest_day = q(HOTTEST_DAY_SQL)
short_days = q(SHORT_DAYS_SQL, {"full_day": 288})
hot_counts = q(HOT_COUNTS_SQL, {"hot_f": 90})
longest_days = q(LONGEST_DAYS_SQL)
full_run_days = q(FULL_RUN_DAYS_SQL)
challenge = q(CHALLENGE_SQL)
n_days = len(daily_counts)

# How does SQLite group? Grouping by an expression of the key needs a temporary sorted structure.
PLAN_SQL = "SELECT date(timestamp_utc) AS day, avg(outside_air_temp_f) FROM ahu_1 GROUP BY day"
plan = " | ".join(r[-1] for r in conn.execute("EXPLAIN QUERY PLAN " + PLAN_SQL))

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
print(f"\ndays that ever passed 90 F: {len(hot_counts)} of {n_days}")
print("\nthe three longest fan run days (hours):")
print(longest_days.round(1).to_string(index=False))
print(f"days the fan ran all 24 hours: {len(full_run_days)} of {n_days}")
print("\nWeek 1 challenge, per AHU and month:")
print(challenge.round({"avg_oat_f": 1, "fan_run_hours": 1}).to_string(index=False))
print("\nquery plan for GROUP BY day:", plan)
