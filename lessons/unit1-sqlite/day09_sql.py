"""Day 9, SQL: time buckets. Hourly and daily averages, and a view vs a summary table.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day09_sql.py

The same computation as day09_pandas.py, done by SQLite on the same rows. A bucket is "which hour
(day) does this 5-minute row belong to": `unixepoch(ts) / 3600` (integer division) or `strftime`
(text) say it in SQL.
Compare the printout with day09_pandas.py: the numbers should match.
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

PARAMS = {
    "pa_per_inh2o": 249.08891
}  # Day 6: the historian logged inches of water; fault math is SI

# 1 + 2. Stack both AHUs and convert to SI. ahu_1 and ahu_2 are the CSVs loaded as tables.
#        static_running_pa is NULL while the fan is off; avg() skips NULLs.
#        (CREATE VIEW can't take bound parameters, so the constant is spliced into the text.)
H_VIEW_SQL = """
CREATE TEMP VIEW h AS
SELECT 'AHU_1' AS equipment_id, timestamp_utc, supply_fan_status,
       (outside_air_temp_f - 32) * 5 / 9.0 AS outside_air_temp_c,
       CASE WHEN supply_fan_status = 1 THEN da_p_inwc * {pa} END AS static_running_pa
FROM ahu_1
UNION ALL
SELECT 'AHU_2', timestamp_utc, supply_fan_status,
       (outside_air_temp_f - 32) * 5 / 9.0,
       CASE WHEN supply_fan_status = 1 THEN da_p_inwc * {pa} END
FROM ahu_2
"""
conn.execute(H_VIEW_SQL.format(pa=repr(PARAMS["pa_per_inh2o"])))

# 3. Hourly: integer division. unixepoch() is seconds since 1970; / 3600 (integers) is "hours since
#    1970".
#    The bucket is turned back into text, in the same format as timestamp_utc, for display.
HOURLY_SELECT = """
SELECT equipment_id,
       strftime('%Y-%m-%d %H:%M:%S+00:00', unixepoch(timestamp_utc) / 3600 * 3600, 'unixepoch')
         AS hour_start,
       count(*) AS rows,
       avg(outside_air_temp_c)  AS mean_oa_c,
       avg(static_running_pa)   AS mean_static_running_pa,
       avg(supply_fan_status)   AS fan_on_fraction
FROM h
GROUP BY equipment_id, unixepoch(timestamp_utc) / 3600
"""

# 4. Daily: the same, with strftime (text) as the bucket
DAILY_SQL = """
SELECT equipment_id, strftime('%Y-%m-%d', timestamp_utc) AS day,
       count(*) AS rows,
       avg(outside_air_temp_c)  AS mean_oa_c,
       avg(static_running_pa)   AS mean_static_running_pa,
       avg(supply_fan_status)   AS fan_on_fraction
FROM h
GROUP BY equipment_id, strftime('%Y-%m-%d', timestamp_utc)
ORDER BY equipment_id, day
"""

# 5. The same hourly buckets by text and by integer division: they must find the same number of
#    buckets
BUCKET_CHECK_SQL = """
SELECT equipment_id,
       count(DISTINCT strftime('%Y-%m-%d %H', timestamp_utc)) AS hour_buckets_floor,
       count(DISTINCT unixepoch(timestamp_utc) / 3600)        AS hour_buckets_int
FROM h
GROUP BY equipment_id
ORDER BY equipment_id
"""

# 6. A view stores the query (every read recomputes); a summary table stores the rows (computed
#    once).
conn.execute("CREATE TEMP VIEW hourly_v AS " + HOURLY_SELECT)
conn.execute("CREATE TEMP TABLE hourly_t AS " + HOURLY_SELECT)
conn.execute("CREATE INDEX temp.hourly_t_eq_hour ON hourly_t (equipment_id, hour_start)")
JULY1_SQL = """
SELECT * FROM hourly_t
WHERE equipment_id = 'AHU_1' AND hour_start >= '2026-07-01' AND hour_start < '2026-07-02'
ORDER BY hour_start
"""

hourly = pd.read_sql_query("SELECT * FROM hourly_t ORDER BY equipment_id, hour_start", conn)
daily = pd.read_sql_query(DAILY_SQL, conn)
bucket_check = pd.read_sql_query(BUCKET_CHECK_SQL, conn)
july1 = pd.read_sql_query(JULY1_SQL, conn)

RESULTS = {"hourly": hourly, "daily": daily, "bucket_check": bucket_check, "ahu_1_july_1": july1}

print("Hourly averages, first rows (AHU_1):")
print(hourly[hourly.equipment_id == "AHU_1"].head(3).round(2).to_string(index=False))
print("\nDaily averages, first rows (AHU_1):")
print(daily[daily.equipment_id == "AHU_1"].head(3).round(2).to_string(index=False))
print(f"\nhourly rows: {len(hourly):,}, daily rows: {len(daily):,}")
print("\nSame hourly buckets by text and by integer division:")
print(bucket_check.to_string(index=False))
n_hourly = conn.execute("SELECT count(mean_oa_c) FROM hourly_t").fetchone()[0]
print(f"hourly means: {n_hourly:,}")
print("\nAHU_1, 2026-07-01, mean outside air by hour (C):")
print(july1.set_index(july1["hour_start"].str[11:16])["mean_oa_c"].round(1).to_string())

# Timing (not part of RESULTS): view = compute on every read; summary table = compute once.
READS = 10
READ_VIEW = "SELECT avg(mean_oa_c), max(mean_oa_c) FROM hourly_v WHERE equipment_id = 'AHU_1'"
READ_TABLE = "SELECT avg(mean_oa_c), max(mean_oa_c) FROM hourly_t WHERE equipment_id = 'AHU_1'"
t0 = time.perf_counter()
for _ in range(READS):
    conn.execute(READ_VIEW).fetchall()
t_view = time.perf_counter() - t0
t0 = time.perf_counter()
for _ in range(READS):
    conn.execute(READ_TABLE).fetchall()
t_table = time.perf_counter() - t0
print(f"\n{READS} reads, recompute each time:   {t_view * 1000:8.1f} ms  (view)")
print(f"{READS} reads, compute once and keep: {t_table * 1000:8.1f} ms  (summary table)")
