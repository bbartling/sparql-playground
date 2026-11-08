"""Day 19, SQL side: the as-of join (latest weather at or before each row) and a weather rule.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit2-python/day19_sql.py

The same computation as day19_pandas.py on the same rows. For each 5-minute AHU row, a correlated
subquery looks up the newest weather row at or before its time, but only one at most TOL_S old. With
an index on the weather timestamps each lookup is a B-tree range seek: O(N log M). Without the index
it scans the whole weather table per row: O(N*M). `EXPLAIN QUERY PLAN` shows the difference.

The weather is a stand-in feed made from AHU_1's own outdoor sensor (see make_weather). pandas
builds it as input data and it is loaded into the `wx` table. SQLite does the joins and the rule.
"""

import os
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)

PARAMS = {
    "tol": 2 * 3600,  # weather older than this is stale
    "diff": 3.0,  # sensor-vs-weather disagreement, degrees C
    "confirm": 6,  # 6 x 5 min = 30 minutes
}


def make_weather(ts, temp_c, seed=3):
    """A stand-in weather feed: hourly means of a sensor (+ 0.5 C noise), with some hours missing.

    Real weather never matches a sensor exactly, and real feeds have failures: 12% of the hours are
    deleted and one 6-hour block is missing. In production this table is the Open-Meteo feed.
    """
    rng = np.random.default_rng(seed)
    hour = (np.asarray(ts) // 3600) * 3600
    wx = pd.DataFrame({"ts": hour, "t": np.asarray(temp_c)}).groupby("ts").t.mean()
    wx = wx.rename("wx_oat").reset_index()
    wx["wx_oat"] = (wx.wx_oat + rng.normal(0, 0.5, len(wx))).round(2)
    wx = wx[rng.random(len(wx)) >= 0.12]
    return wx[~wx.index.isin(range(len(wx) // 2, len(wx) // 2 + 6))].reset_index(drop=True)


# 1. Load: both AHUs' tables (the CSVs), the columns we need, in SI. ts is epoch seconds
#    (unixepoch parses the text timestamps). Setup: a temp table with an index.
conn.execute("DROP TABLE IF EXISTS temp.h")
conn.execute(
    """
CREATE TEMP TABLE h AS
SELECT 'AHU_1' AS equipment_id, unixepoch(timestamp_utc) AS ts,
       (outside_air_temp_f - 32.0) * 5.0 / 9.0 AS oat_c, supply_fan_status AS fan_status
FROM ahu_1
UNION ALL
SELECT 'AHU_2', unixepoch(timestamp_utc), (outside_air_temp_f - 32.0) * 5.0 / 9.0,
       supply_fan_status
FROM ahu_2
"""
)
conn.execute("CREATE INDEX temp.h_eq_ts ON h (equipment_id, ts)")

# 2. The stand-in weather feed, from AHU_1's own sensor. Two copies of the same rows: `wx` with an
#    index on ts, `wx_plain` without.
a1 = pd.read_sql_query("SELECT ts, oat_c FROM h WHERE equipment_id = 'AHU_1' ORDER BY ts", conn)
wx = make_weather(a1.ts, a1.oat_c)
for table in ("wx", "wx_plain"):
    conn.execute(f"DROP TABLE IF EXISTS temp.{table}")
    conn.execute(f"CREATE TEMP TABLE {table} (ts INTEGER, wx_oat REAL)")
    conn.executemany(f"INSERT INTO {table} VALUES (?, ?)", wx.itertuples(index=False, name=None))
conn.execute("CREATE INDEX temp.wx_ts ON wx (ts)")
n_rows = conn.execute("SELECT count(*) FROM h").fetchone()[0]
print(f"{n_rows:,} AHU rows, {len(wx):,} weather rows (of {len(a1) * 300 // 3600:,} hours)")


# 3. The as-of join. The inner query runs once per AHU row, which makes it "correlated".
def join_sql(table="wx"):
    return f"""
SELECT j.equipment_id, j.ts, j.oat_c, j.fan_status, j.wx_ts, w.wx_oat
FROM (
  SELECT h.equipment_id, h.ts, h.oat_c, h.fan_status,
         (SELECT w.ts FROM {table} w
          WHERE w.ts <= h.ts AND w.ts >= h.ts - :tol
          ORDER BY w.ts DESC LIMIT 1) AS wx_ts
  FROM h
) j
LEFT JOIN {table} w ON w.ts = j.wx_ts
"""


# 4. Sensor-versus-weather rule: the join as a CTE under Day 14's streak machinery.
#    No weather (stale or missing) means unknown, so no fault.
RULE_SQL = f"""
WITH j AS ({join_sql()}), base AS (
  SELECT equipment_id, ts, wx_oat,
         CASE WHEN fan_status = 1 AND wx_oat IS NOT NULL AND ABS(oat_c - wx_oat) > :diff
              THEN 1 ELSE 0 END AS raw_fault
  FROM j
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                 THEN 0 ELSE 1 END AS new_streak
  FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len
  FROM streaks
)
SELECT equipment_id, ts, wx_oat, raw_fault, streak_id,
       CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
FROM ranked
"""
HOURS_SQL = f"""
SELECT equipment_id, SUM(fault) AS fault_rows, SUM(raw_fault) AS raw_rows,
       SUM(fault) * 5 / 60.0 AS fault_hours
FROM ({RULE_SQL})
GROUP BY equipment_id ORDER BY equipment_id
"""


def query(sql, **override):
    return pd.read_sql_query(sql, conn, params={**PARAMS, **override})


asof_join = query(join_sql())
print(asof_join.sort_values(["equipment_id", "ts"]).head(3).to_string(index=False))
print("rows with no usable weather:", int(asof_join.wx_ts.isna().sum()))
rule_hours = query(HOURS_SQL).astype({"fault_rows": "int64", "raw_rows": "int64"})
rule_hours = rule_hours[["equipment_id", "fault_rows", "raw_rows", "fault_hours"]]

# 5. Try it 1: tighten the tolerance to 1 hour. How many rows lose their weather?
NO_WEATHER_SQL = f"SELECT count(*) - count(wx_ts) AS n FROM ({join_sql()})"
no_weather = pd.DataFrame(
    [
        {"tol_s": t, "rows_without_weather": int(query(NO_WEATHER_SQL, tol=t).n[0])}
        for t in (7200, 3600)
    ]
)

# 6. How the database does it: EXPLAIN QUERY PLAN (Day 12). With the index, each probe is a B-tree
#    range seek; without it, a full scan of the weather table per AHU row.
plans = {t: query("EXPLAIN QUERY PLAN " + join_sql(t)).detail.tolist() for t in ("wx", "wx_plain")}

# 7. Timing on synthetic rows (one AHU; weather one hour per 12 rows). The unindexed query is
#    O(N*M), so it stops at 10,000 rows. NaN means "not run". Loading the tables is setup.
COUNT_SQL = """
SELECT COUNT(wx_ts) AS matched FROM (
  SELECT (SELECT w.ts FROM {t} w WHERE w.ts <= h.ts AND w.ts >= h.ts - :tol
          ORDER BY w.ts DESC LIMIT 1) AS wx_ts
  FROM h)
"""
timing, matches = [], []
for n in lab.sizes([1_000, 10_000, 100_000, 1_000_000]):
    d = lab.synthetic_history(n)
    w = make_weather(d.ts, d.oat)
    mem = sqlite3.connect(":memory:")
    lab.to_sqlite(d[["ts"]], mem, "h")  # the timing only needs the timestamps
    lab.to_sqlite(w, mem, "wx", index=["ts"])  # indexed
    lab.to_sqlite(w, mem, "wx_plain")  # the same rows, no index
    reps = 3 if n <= 100_000 else 1
    row = {"N": n, "M": len(w)}

    def run(table, mem=mem):
        return mem.execute(COUNT_SQL.format(t=table), {"tol": PARAMS["tol"]}).fetchone()[0]

    row["sql_index_s"] = lab.best_time(lambda run=run: run("wx"), reps)
    if n <= 10_000:  # the O(N*M) case
        row["sql_noindex_s"] = lab.best_time(lambda run=run: run("wx_plain"), reps)
    timing.append(row)
    matches.append({"N": n, "M": len(w), "matched": run("wx")})
    mem.close()
timing = pd.DataFrame(timing).reindex(columns=["N", "M", "sql_noindex_s", "sql_index_s"])
timing_matches = pd.DataFrame(matches)

RESULTS = {
    "asof_join": asof_join,
    "oat_meteo_hours": rule_hours,
    "rows_without_weather": no_weather,
    "timing_matches": timing_matches,
}

print("\nSensor vs weather rule (fan running, |sensor - weather| > 3 C for 30 minutes):")
print(rule_hours.round(2).to_string(index=False))
print("\nRows without weather by tolerance:")
print(no_weather.to_string(index=False))
for table, plan in plans.items():
    print(f"\nEXPLAIN QUERY PLAN with {table}:")
    for line in plan:
        print("  ", line)
print("\nTiming, seconds (times vary by machine):")
print(timing.to_string(index=False, float_format=lambda x: f"{x:,.4g}"))
print("\nMatched rows at every size (the pandas script finds the same numbers):")
print(timing_matches.to_string(index=False))
