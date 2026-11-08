"""Day 10, SQL: Open-FDD's results. Episodes per rule, then tag every 5-minute row with its episode.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day10_sql.py

The same computation as day10_pandas.py, done by SQLite on the same rows. `fdd_events` holds one
row per fault *episode* (start, end, rule). The interval join asks, for each 5-minute history row:
which episode(s) is this timestamp inside? A `BETWEEN` join counts all of them; an "as-of" lookup
finds the latest-starting one.
Compare the printout with day10_pandas.py: the numbers should match.
"""

import os
import sqlite3
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)

PARAMS = {"rule": "fc13"}  # which Open-FDD rule to tag the rows with

# 1. Load: Open-FDD's episodes with an equipment_id, indexed for range lookups; history timestamps
#    for both AHUs.
#    The timestamps are ISO text in one format, so comparing the text compares them in time order.
conn.execute(
    """
    CREATE TEMP TABLE ev AS
    SELECT replace(hvac_system, 'bld_50_', '') AS equipment_id, rule_name,
           start_time_utc, end_time_utc,
           duration_min
    FROM fdd_events
    """
)
conn.execute("CREATE INDEX temp.ev_eq_start ON ev (equipment_id, start_time_utc)")
conn.execute(
    """
    CREATE TEMP VIEW h AS
    SELECT 'AHU_1' AS equipment_id, timestamp_utc FROM ahu_1
    UNION ALL
    SELECT 'AHU_2', timestamp_utc FROM ahu_2
    """
)

# 2. Episodes and hours per rule: GROUP BY two keys
RULE_SUMMARY_SQL = """
SELECT equipment_id, rule_name, count(*) AS episodes, sum(duration_min) / 60.0 AS hours
FROM ev
GROUP BY equipment_id, rule_name
ORDER BY equipment_id, rule_name
"""

# 3. Interval join, version 1: a BETWEEN join. Each row pairs with every episode that contains it,
#    and
#    GROUP BY row + count() gives the number of episodes open at that time. A row inside no episode
#    survives because of the LEFT JOIN (count(e.start_time_utc) skips the NULL).
OPEN_COUNT_SQL = """
CREATE TEMP TABLE open_count AS
SELECT r.equipment_id, r.timestamp_utc, count(e.start_time_utc) AS episodes_open
FROM h r
LEFT JOIN ev e
  ON e.equipment_id = r.equipment_id
 AND e.rule_name = :rule
 AND r.timestamp_utc BETWEEN e.start_time_utc AND e.end_time_utc
GROUP BY r.equipment_id, r.timestamp_utc
"""
conn.execute(OPEN_COUNT_SQL, PARAMS)

# 4. Interval join, version 2: an "as-of" lookup. Seek the latest episode that started at or before
#    the row
#    (an index seek on ev), keep it only if it has not ended yet. One episode per row, so with
#    overlapping
#    episodes it can miss a row that an earlier, longer episode still covers.
TAGGED_SQL = """
CREATE TEMP TABLE tagged AS
WITH last AS (
  SELECT r.equipment_id, r.timestamp_utc,
         (SELECT max(e.start_time_utc) FROM ev e
          WHERE e.equipment_id = r.equipment_id AND e.rule_name = :rule
            AND e.start_time_utc <= r.timestamp_utc) AS last_start
  FROM h r
)
SELECT l.equipment_id, l.timestamp_utc, o.episodes_open,
       (SELECT CASE WHEN e.end_time_utc >= l.timestamp_utc THEN e.start_time_utc END
        FROM ev e
        WHERE e.equipment_id = l.equipment_id AND e.rule_name = :rule
          AND e.start_time_utc = l.last_start) AS latest_start
FROM last l
JOIN open_count o ON o.equipment_id = l.equipment_id AND o.timestamp_utc = l.timestamp_utc
"""
conn.execute(TAGGED_SQL, PARAMS)

# 5. Rows covered vs episode hours. 5-minute rows x 5 / 60 = hours the rule was "open"
SUMMARY_SQL = """
SELECT t.equipment_id,
       count(*) AS rows,
       sum(t.episodes_open > 0) AS rows_in_episode,
       max(t.episodes_open) AS max_open,
       sum(t.episodes_open > 0 AND t.latest_start IS NULL) AS rows_missed_by_asof,
       sum(t.episodes_open > 0) * 5 / 60.0 AS covered_h,
       (SELECT sum(duration_min) / 60.0 FROM ev e
        WHERE e.equipment_id = t.equipment_id AND e.rule_name = :rule) AS episode_hours_summed
FROM tagged t
GROUP BY t.equipment_id
ORDER BY t.equipment_id
"""

rule_summary = pd.read_sql_query(RULE_SUMMARY_SQL, conn)
tagged = pd.read_sql_query("SELECT * FROM tagged ORDER BY equipment_id, timestamp_utc", conn)
tagged_summary = pd.read_sql_query(SUMMARY_SQL, conn, params=PARAMS)

RESULTS = {"rule_summary": rule_summary, "tagged": tagged, "tagged_summary": tagged_summary}

print("Open-FDD episodes and hours per rule:")
print(rule_summary.round(1).to_string(index=False))
print(f"\nEvery 5-minute row tagged with its {PARAMS['rule']} episodes:")
print(tagged_summary.round(1).to_string(index=False))
print(tagged[tagged["episodes_open"] > 0].head(3).to_string(index=False))

# Plan and timing (not part of RESULTS): the BETWEEN join and the as-of lookup both seek into ev's
#    index.
BETWEEN_PLAN = OPEN_COUNT_SQL.replace("CREATE TEMP TABLE open_count AS", "")
print("\nQuery plan for the BETWEEN join (the lines about ev):")
for row in conn.execute("EXPLAIN QUERY PLAN" + BETWEEN_PLAN, PARAMS):
    if "ev" in row[3]:
        print("  ", row[3])
t0 = time.perf_counter()
conn.execute("DROP TABLE temp.open_count")
conn.execute(OPEN_COUNT_SQL, PARAMS)
t_between = time.perf_counter() - t0
t0 = time.perf_counter()
conn.execute("DROP TABLE temp.tagged")
conn.execute(TAGGED_SQL, PARAMS)
t_asof = time.perf_counter() - t0
print(f"\nBETWEEN join, count of open episodes:  {t_between * 1000:7.1f} ms")
print(f"as-of lookup + count (both steps):      {t_asof * 1000:7.1f} ms")
