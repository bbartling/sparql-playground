"""Day 7, SQL: stack two AHUs, then join them on time to compare their outside-air sensors.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day07_sql.py

The same computation as day07_pandas.py, done by SQLite on the same rows. SQLite does all the
work; pandas only turns the result rows into a table for printing.
Compare the printout with day07_pandas.py: the numbers should match.
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

PARAMS = {"day_end": "2026-03-17"}  # the explosion demo uses the first day only

# 1 + 2. Stack (UNION ALL) and convert to SI (Day 6). ahu_1 and ahu_2 are the CSVs loaded as tables.
STACK_VIEW_SQL = """
CREATE TEMP VIEW stacked AS
SELECT 'AHU_1' AS equipment_id, timestamp_utc,
       (outside_air_temp_f - 32) * 5 / 9.0 AS outside_air_temp_c
FROM ahu_1
UNION ALL
SELECT 'AHU_2', timestamp_utc, (outside_air_temp_f - 32) * 5 / 9.0
FROM ahu_2
"""
conn.execute(STACK_VIEW_SQL)

# 3. What the stacked table holds, per AHU
STACK_SUMMARY_SQL = """
SELECT equipment_id, count(*) AS rows,
       min(timestamp_utc) AS first_ts, max(timestamp_utc) AS last_ts,
       avg(outside_air_temp_c) AS mean_oa_c, min(outside_air_temp_c) AS min_oa_c
FROM stacked
GROUP BY equipment_id
ORDER BY equipment_id
"""

# 4. Join on timestamp: one row per timestamp, one column per AHU. For each ahu_1 row SQLite SEEKS
#    the matching
#    ahu_2 row through the primary key's B-tree (an index nested-loop join): O(n log m).
JOIN_SQL = """
FROM ahu_1 a
JOIN ahu_2 b ON b.timestamp_utc = a.timestamp_utc
"""
PAIRS_SQL = f"""
CREATE TEMP VIEW pairs AS
SELECT a.timestamp_utc,
       (a.outside_air_temp_f - 32) * 5 / 9.0 AS oa_ahu_1_c,
       (b.outside_air_temp_f - 32) * 5 / 9.0 AS oa_ahu_2_c,
       (a.outside_air_temp_f - 32) * 5 / 9.0 - (b.outside_air_temp_f - 32) * 5 / 9.0 AS diff_k
{JOIN_SQL}
"""
conn.execute(PAIRS_SQL)

# 5. How far apart are they?
GAP_SQL = """
SELECT count(*) AS paired_rows,
       avg(abs(diff_k)) AS mean_abs_diff_k,
       max(abs(diff_k)) AS max_abs_diff_k,
       sum(abs(diff_k) > 2)  AS rows_over_2k,
       sum(abs(diff_k) > 20) AS rows_over_20k
FROM pairs
"""

# 6. Join explosion: the first day (280 rows per AHU), joined on the HOUR instead of the timestamp.
#    The hour repeats 12 times per AHU, so every row matches 12 rows on the other side.
#    SQL has no validate="1:1"; the equivalent is checking that the join key is unique.
EXPLOSION_SQL = """
WITH da AS (SELECT timestamp_utc, substr(timestamp_utc, 1, 13) AS hour FROM ahu_1
            WHERE timestamp_utc < :day_end),
     db AS (SELECT timestamp_utc, substr(timestamp_utc, 1, 13) AS hour FROM ahu_2
            WHERE timestamp_utc < :day_end)
SELECT (SELECT count(*) FROM da) AS rows_per_side,
       (SELECT count(*) FROM da JOIN db ON db.timestamp_utc = da.timestamp_utc)
         AS joined_on_timestamp,
       (SELECT count(*) FROM da JOIN db ON db.hour = da.hour) AS joined_on_hour,
       (SELECT count(*) > count(DISTINCT hour) FROM db) AS validate_blocked
"""

stack_summary = pd.read_sql_query(STACK_SUMMARY_SQL, conn)
pairs = pd.read_sql_query("SELECT * FROM pairs ORDER BY timestamp_utc", conn)
gap = pd.read_sql_query(GAP_SQL, conn)
explosion = pd.read_sql_query(EXPLOSION_SQL, conn, params=PARAMS)

RESULTS = {
    "stack_summary": stack_summary,
    "oa_pairs": pairs,
    "oa_gap": gap,
    "explosion": explosion,
}

print("Stacked table, per AHU:")
print(stack_summary.round(2).to_string(index=False))
print("\nOutside-air temperature, AHU_1 minus AHU_2 (K):")
print(gap.round(2).to_string(index=False))
print("\nJoin explosion on one day of data:")
print(explosion.to_string(index=False))

# The plans and a timing (not part of RESULTS): how SQLite runs the join.
conn.execute("CREATE TEMP TABLE a_plain AS SELECT timestamp_utc, outside_air_temp_f FROM ahu_1")
conn.execute("CREATE TEMP TABLE b_plain AS SELECT timestamp_utc, outside_air_temp_f FROM ahu_2")
COUNT_PLAIN = "SELECT count(*) FROM a_plain a JOIN b_plain b ON b.timestamp_utc = a.timestamp_utc"
COUNT_PK = "SELECT count(*) FROM ahu_1 a JOIN ahu_2 b ON b.timestamp_utc = a.timestamp_utc"
print("\nQuery plan, join on the primary key:")
for row in conn.execute("EXPLAIN QUERY PLAN " + COUNT_PK):
    print("  ", row[3])
print("Query plan, join on tables with no index (SQLite builds a temporary one):")
for row in conn.execute("EXPLAIN QUERY PLAN " + COUNT_PLAIN):
    print("  ", row[3])
t0 = time.perf_counter()
conn.execute(COUNT_PK).fetchone()
t_pk = time.perf_counter() - t0
t0 = time.perf_counter()
conn.execute(COUNT_PLAIN).fetchone()
t_auto = time.perf_counter() - t0
print(f"\njoin via primary-key seeks:          {t_pk * 1000:8.1f} ms")
print(f"join via temporary automatic index:  {t_auto * 1000:8.1f} ms")
