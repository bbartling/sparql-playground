# Day 10 — Time buckets and views: hourly averages (what Timescale's `time_bucket` does)

**Goal:** downsample 5-minute data to hourly in SQL and pandas, and save queries as views and summary tables.

## Read

**Time bucketing.** Integer division rounds a timestamp down to a bucket:

```
ts / 3600 * 3600     -- start of the hour (3600 s)
ts / 900  * 900      -- start of the 15-minute bucket
ts / 86400 * 86400   -- start of the UTC day
```

`ts` is an integer, so `/` drops the remainder. Group by the bucket and aggregate, and you have hourly data.
TimescaleDB, the Postgres extension many historians use, calls this `time_bucket('1 hour', time)`. SQLite does it
with arithmetic.

pandas has two spellings of the same idea:

| Idea | SQL | pandas |
|---|---|---|
| bucket start, by arithmetic | `ts / 3600 * 3600` | `ts // 3600 * 3600` |
| bucket start, on datetimes | (`datetime(ts / 3600 * 3600, 'unixepoch')`) | `dt.floor("h")` |
| bucket and aggregate | `GROUP BY ts / 3600` | `groupby(bucket)`, or `resample("1h", on="time")` |
| several aggregates | `avg(v), min(v), max(v), count(*)` | `.agg(mean="mean", lo="min", hi="max", n="size")` |

Beware the integer division. In SQL, `/` on two integers truncates toward zero, which equals "round down" only for
non-negative timestamps (every timestamp here). Python's `//` always floors, so the two would differ for dates before
1970. Neither bothers you today.

Each of these is a **hash aggregation**: one pass over the n rows, O(n), with a hash table holding one entry per
bucket. SQL's `GROUP BY` on an expression can't use an index (the bucket is computed, not stored), so SQLite
collects the groups in a temporary B-tree: O(n log b) for b buckets. `resample` instead needs sorted time, which a
DataFrame sorted by `ts` already has.

Always keep a `count(*)` per bucket. A bucket with 4 readings instead of 12 is a partial hour, and its average is less
trustworthy.

**Views.** `CREATE VIEW name AS SELECT ...` saves a query under a name. It stores no data; it reruns every time you
use it. Good for not repeating yourself. The pandas analogue is a **function**: `reading(roles)` that loads and merges
whenever you call it.

**Summary tables.** `CREATE TABLE name AS SELECT ...` runs the query once and stores the result. It's fast to read,
but stale when new data arrives. In pandas it's a DataFrame you keep in a variable (or write to a file). Timescale's
**continuous aggregates** are this idea maintained for you: a summary table it refreshes as new data lands. In SQLite
you rebuild it yourself. The trade is **compute once, read many** (table) against **always fresh, pay every time**
(view). We measure it below.

Units: raw (°F, inH2O, percent 0–100).

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_points(conn)
pts = lab.query(conn, "SELECT * FROM lab_point")
ROLE_COLS = pts[["timeseries_id", "equipment_id", "openfdd_role"]]
KEYS = ["equipment_id", "ts"]
ALL_ROLES = sorted(pts["openfdd_role"].dropna().unique())  # the 13 roles: 26 points, 924k readings


def role_samples(roles):
    """Readings of just the points that carry one of these roles, labelled with equipment and role."""
    ids = pts.loc[pts.openfdd_role.isin(roles), "timeseries_id"].tolist()
    marks = ",".join("?" * len(ids))
    raw = lab.query(
        conn, f"SELECT timeseries_id, ts, value FROM samples WHERE timeseries_id IN ({marks})", ids
    )
    return raw.merge(ROLE_COLS, on="timeseries_id", validate="m:1").drop(columns="timeseries_id")
```

**Hourly outside air temperature, AHU_1.** First in SQL (the lookup in the `WHERE` finds the point by role, so no
UUID is typed), then with arithmetic bucketing in pandas, then with `resample`.

```python
HOURLY_SQL = """
SELECT ts / 3600 * 3600 AS hour_ts,
       avg(value) AS avg_f,
       count(*) AS n
FROM samples
WHERE timeseries_id = (SELECT timeseries_id FROM lab_point
                       WHERE equipment_id = 'AHU_1' AND openfdd_role = 'outside-air-temp')
GROUP BY ts / 3600
ORDER BY ts / 3600
"""
hourly_sql = lab.query(conn, HOURLY_SQL)

oat = role_samples(["outside-air-temp"]).query("equipment_id == 'AHU_1'").sort_values("ts")
oat = oat.assign(hour_ts=oat["ts"] // 3600 * 3600)  # bucket start, by arithmetic
hourly_pd = oat.groupby("hour_ts")["value"].agg(avg_f="mean", n="size").reset_index()
lab.assert_parity(hourly_pd, hourly_sql, label="hourly OAT (arithmetic bucket)")

# resample works on a datetime index; convert back to epoch seconds to compare
by_time = oat.assign(time=pd.to_datetime(oat["ts"], unit="s")).set_index("time")["value"]
res = by_time.resample("1h").agg(["mean", "size"])
res_pd = pd.DataFrame(
    {
        "hour_ts": (res.index - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s"),
        "avg_f": res["mean"].to_numpy(),
        "n": res["size"].to_numpy(),
    }
)
assert (res_pd.n > 0).all()  # resample would also emit empty hours; this historian has no gaps
lab.assert_parity(res_pd, hourly_sql, label="hourly OAT (resample)")

first = hourly_sql.iloc[0]
print(pd.to_datetime(first.hour_ts, unit="s"), round(first.avg_f, 2), int(first.n))
assert (pd.to_datetime(first.hour_ts, unit="s").isoformat(), round(first.avg_f, 2), first.n) == (
    "2026-03-16T00:00:00",
    69.03,
    4,
)
```

The first hour has only 4 readings (00:40–00:55), which is why `n` is kept. (`resample` fills in missing hours with
`NaN` and a count of 0; SQL's `GROUP BY` only makes groups for hours that have data. Both agree here because the
historian has no gaps.)

**A view, and its pandas twin, a function.** Every reading with its point attributes.

```python
conn.execute("DROP VIEW IF EXISTS lab_reading")
conn.execute(
    """CREATE VIEW lab_reading AS
       SELECT p.equipment_id, p.openfdd_role, p.point_id, p.unit, s.ts, s.value
       FROM samples s
       JOIN lab_point p ON p.timeseries_id = s.timeseries_id"""
)

fan_sql = lab.query(
    conn,
    "SELECT equipment_id, count(*) AS n FROM lab_reading WHERE openfdd_role = 'fan-status' GROUP BY 1",
)
n_view = conn.execute(
    "SELECT count(*) FROM lab_reading WHERE openfdd_role = 'fan-status'"
).fetchone()[0]
fan_pd = role_samples(["fan-status"]).groupby("equipment_id").size().rename("n").reset_index()
lab.assert_parity(fan_pd, fan_sql, label="view vs function")
print("fan-status readings:", n_view)
assert n_view == 71072
```

`WHERE openfdd_role = 'fan-status'` on the view is pushed down into the view's own join, so SQLite still only touches
the fan readings. The view stores nothing, and the next query joins again.

**A summary table, and its pandas twin, a stored DataFrame.** Hourly mean, min and max for every role point.

```python
HOURLY_ALL_SQL = """
SELECT equipment_id, openfdd_role,
       ts / 3600 * 3600 AS hour_ts,
       avg(value) AS mean, min(value) AS lo, max(value) AS hi, count(*) AS n
FROM lab_reading
WHERE openfdd_role IS NOT NULL
GROUP BY equipment_id, openfdd_role, ts / 3600
"""
conn.execute("DROP TABLE IF EXISTS lab_hourly")
conn.execute("CREATE TABLE lab_hourly AS " + HOURLY_ALL_SQL)
conn.execute("CREATE INDEX lab_hourly_idx ON lab_hourly (equipment_id, openfdd_role, hour_ts)")
conn.commit()

allr = role_samples(ALL_ROLES)
allr["hour_ts"] = allr["ts"] // 3600 * 3600
hourly_all_pd = (
    allr.groupby(["equipment_id", "openfdd_role", "hour_ts"])["value"]
    .agg(mean="mean", lo="min", hi="max", n="size")
    .reset_index()
)
lab_hourly = lab.query(conn, "SELECT * FROM lab_hourly")
lab.assert_parity(
    hourly_all_pd, lab_hourly, keys=["equipment_id", "openfdd_role", "hour_ts"], label="lab_hourly"
)
print(len(lab_hourly), "rows in lab_hourly,", len(allr), "readings in the DataFrame")
assert len(lab_hourly) == 77012
```

26 role points × 2,962 hours = 77,012 rows, instead of 924k readings. Charts and dashboards read tables like this.

**View vs table, measured.** Ask the same question both ways: AHU_2's hourly duct static, as a daily maximum of the
hourly mean. The view version recomputes the join and the bucketing every time. The table version reads rows that are
already bucketed (and finds them through the index we just made).

```python
ASK_VIEW = """
SELECT date(hour_ts, 'unixepoch') AS day, max(mean) AS peak
FROM (SELECT ts / 3600 * 3600 AS hour_ts, avg(value) AS mean
      FROM lab_reading
      WHERE equipment_id = 'AHU_2' AND openfdd_role = 'duct-static-pressure'
      GROUP BY ts / 3600)
GROUP BY day ORDER BY day
"""
ASK_TABLE = """
SELECT date(hour_ts, 'unixepoch') AS day, max(mean) AS peak
FROM lab_hourly
WHERE equipment_id = 'AHU_2' AND openfdd_role = 'duct-static-pressure'
GROUP BY day ORDER BY day
"""
via_view, via_table = lab.query(conn, ASK_VIEW), lab.query(conn, ASK_TABLE)
lab.assert_parity(via_view, via_table, label="same answer from the view and the table")

t_view = lab.best_time(lambda: conn.execute(ASK_VIEW).fetchall())
t_table = lab.best_time(lambda: conn.execute(ASK_TABLE).fetchall())
print(
    f"view {t_view * 1000:7.1f} ms | table {t_table * 1000:6.1f} ms | table is {t_view / t_table:.0f}x faster"
)
assert t_table < t_view
```

The view must scan all 35,536 AHU_2 static readings each time (O(n)). The table scans about 2,962 hourly rows via
the index, about n/12 rows with no join. The cost the table hides is staleness:

```python
conn.execute("CREATE TEMP TABLE t (x INTEGER)")
conn.execute("INSERT INTO t VALUES (1), (2)")
conn.execute("CREATE TEMP VIEW t_view AS SELECT sum(x) AS total FROM t")
conn.execute("CREATE TEMP TABLE t_table AS SELECT sum(x) AS total FROM t")
conn.execute("INSERT INTO t VALUES (3)")  # new data arrives
print(
    "view:",
    conn.execute("SELECT total FROM t_view").fetchone()[0],
    "| table:",
    conn.execute("SELECT total FROM t_table").fetchone()[0],
)
assert conn.execute("SELECT total FROM t_view").fetchone()[0] == 6
assert conn.execute("SELECT total FROM t_table").fetchone()[0] == 3  # stale until rebuilt
```

The view sees the new row at once; the table still says 3 until you rebuild it. Dashboards often accept that:
rebuild hourly, read instantly. Timescale's continuous aggregates automate the rebuild.

## Try it

1. From `lab_hourly`, the hour with AHU_2's highest average duct static pressure.
2. Write a 15-minute bucket version of the first query. How many readings does a full 15-minute bucket have?

<details><summary>Answers</summary>

```python
TOP_SQL = """
SELECT hour_ts, mean
FROM lab_hourly
WHERE equipment_id = 'AHU_2' AND openfdd_role = 'duct-static-pressure'
ORDER BY mean DESC
LIMIT 1
"""
top_sql = lab.query(conn, TOP_SQL)
ahu2 = hourly_all_pd[
    (hourly_all_pd.equipment_id == "AHU_2") & (hourly_all_pd.openfdd_role == "duct-static-pressure")
]
top_pd = ahu2.nlargest(1, "mean")[["hour_ts", "mean"]]
lab.assert_parity(top_pd, top_sql, label="AHU_2 highest hourly static")
print(pd.to_datetime(top_sql.hour_ts.iloc[0], unit="s"), round(top_sql["mean"].iloc[0], 3))
assert len(top_sql) == 1
```

```python
QUARTER_SQL = """
SELECT ts / 900 * 900 AS bucket, count(*) AS n
FROM samples
WHERE timeseries_id = (SELECT timeseries_id FROM lab_point
                       WHERE equipment_id = 'AHU_1' AND openfdd_role = 'outside-air-temp')
GROUP BY ts / 900 ORDER BY ts / 900
"""
quarter_sql = lab.query(conn, QUARTER_SQL)
quarter_pd = (
    oat.assign(bucket=oat["ts"] // 900 * 900).groupby("bucket").size().rename("n").reset_index()
)
lab.assert_parity(quarter_pd, quarter_sql, label="15-minute buckets")
print(
    quarter_sql.head(3)
    .assign(bucket=lambda d: pd.to_datetime(d.bucket, unit="s"))
    .to_string(index=False)
)
assert quarter_sql.n.iloc[:3].tolist() == [1, 3, 3]
```

A full 15-minute bucket has 3 readings. The first has only one, at 00:40 (the 00:30 bucket).

</details>

## Week 2 challenge

Build `lab_daily`: one row per AHU per day, with fan run hours, hours run while unoccupied, average outside air
temperature, and average static pressure *while running*. Then find the five days with the most unoccupied runtime on
AHU_1, and check the day of week (`strftime('%w', ...)`): weekends?

<details><summary>Answer</summary>

SQL first. It pivots the roles into columns with the conditional aggregation of Day 9, then buckets by day.
pandas does the same with a `pivot` and a `groupby` on the day.

```python
DAILY_SQL = """
WITH wide AS (
  SELECT p.equipment_id, s.ts,
         max(CASE WHEN p.openfdd_role = 'fan-status' THEN s.value END)           AS fan,
         max(CASE WHEN p.openfdd_role = 'occupied' THEN s.value END)             AS occupied,
         max(CASE WHEN p.openfdd_role = 'outside-air-temp' THEN s.value END)     AS oat,
         max(CASE WHEN p.openfdd_role = 'duct-static-pressure' THEN s.value END) AS static
  FROM samples s
  JOIN lab_point p ON p.timeseries_id = s.timeseries_id
  WHERE p.openfdd_role IN ('fan-status', 'occupied', 'outside-air-temp', 'duct-static-pressure')
  GROUP BY p.equipment_id, s.ts
)
SELECT equipment_id,
       date(ts, 'unixepoch')                                                   AS day,
       sum(fan) * 5 / 60.0                                                     AS run_h,
       sum(CASE WHEN fan = 1 AND occupied = 0 THEN 1 ELSE 0 END) * 5 / 60.0    AS run_unocc_h,
       avg(oat)                                                                AS avg_oat,
       avg(CASE WHEN fan = 1 THEN static END)                                  AS avg_static_running
FROM wide
GROUP BY equipment_id, day
"""
conn.execute("DROP TABLE IF EXISTS lab_daily")
conn.execute("CREATE TABLE lab_daily AS " + DAILY_SQL)
conn.commit()
daily_sql = lab.query(conn, "SELECT * FROM lab_daily")

d = role_samples(["fan-status", "occupied", "outside-air-temp", "duct-static-pressure"])
d = d.pivot(index=KEYS, columns="openfdd_role", values="value").reset_index()
d["day"] = pd.to_datetime(d["ts"], unit="s").dt.strftime("%Y-%m-%d")
d["run_unocc"] = (d["fan-status"] == 1) & (d["occupied"] == 0)
d["static_running"] = d["duct-static-pressure"].where(
    d["fan-status"] == 1
)  # NaN when off, skipped by mean
gd = d.groupby(["equipment_id", "day"])
daily_pd = pd.DataFrame(
    {
        "run_h": gd["fan-status"].sum() * 5 / 60,
        "run_unocc_h": gd["run_unocc"].sum() * 5 / 60,
        "avg_oat": gd["outside-air-temp"].mean(),
        "avg_static_running": gd["static_running"].mean(),
    }
).reset_index()
lab.assert_parity(daily_pd, daily_sql, keys=["equipment_id", "day"], label="lab_daily")
print(len(daily_sql), "rows:", daily_sql.groupby("equipment_id").size().to_dict())
assert len(daily_sql) == 2 * 124  # 124 days (Mar 16 to Jul 17) for each AHU
```

Now the five days with the most unoccupied runtime on AHU_1, and their weekday. SQLite's `%w` counts Sunday as 0;
pandas' `dayofweek` counts Monday as 0, so convert before comparing.

```python
TOP5_SQL = """
SELECT day, run_unocc_h, strftime('%w', day) AS dow
FROM lab_daily
WHERE equipment_id = 'AHU_1'
ORDER BY run_unocc_h DESC, day
LIMIT 5
"""
top5_sql = lab.query(conn, TOP5_SQL)

a1 = (
    daily_pd[daily_pd.equipment_id == "AHU_1"]
    .sort_values(["run_unocc_h", "day"], ascending=[False, True])
    .head(5)
)
sunday_first = (pd.to_datetime(a1["day"]).dt.dayofweek + 1) % 7
top5_pd = a1.assign(dow=sunday_first.astype(str))[["day", "run_unocc_h", "dow"]]
lab.assert_parity(top5_pd, top5_sql, keys=["day"], label="top 5 unoccupied days")

NAMES = {"0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed", "4": "Thu", "5": "Fri", "6": "Sat"}
print(top5_sql.assign(weekday=top5_sql.dow.map(NAMES)).to_string(index=False))
```

Not weekends. The heaviest days are Wednesday 2026-05-20 (10.1 h running while unoccupied), Tuesday 2026-04-14
and Monday 2026-05-18, with only one Sunday (2026-05-17) in the top five. The extra unoccupied runtime sits on
weekdays: more likely a schedule that starts the fan early or stops it late than a weekend left running. (The
`ORDER BY run_unocc_h DESC, day` tie-break matters: 2026-05-17 and 2026-06-29 both have 9.17 h.) That's a lead
for a day-by-day look at the occupancy command and fan status.

</details>
