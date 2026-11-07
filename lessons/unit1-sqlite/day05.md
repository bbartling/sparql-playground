# Day 5 — GROUP BY and HAVING: per day, per month, per series

**Goal:** one summary row per group, and keep only the groups you care about, in SQL and in pandas.

## Read

`GROUP BY` splits rows into groups. Each aggregate is then computed once per group:

```
SELECT group_columns, aggregates
FROM ...
WHERE   row filter           -- before grouping
GROUP BY group_columns
HAVING  group filter          -- after grouping, can use aggregates
ORDER BY ...
```

`WHERE` throws away rows before they're grouped. `HAVING` throws away whole groups after. You can't put `avg(...)`
in a `WHERE`, because no group exists yet at that point.

You can group by an expression, such as the date, so `GROUP BY date(ts, 'unixepoch')` gives one row per day. SQLite
lets you use a column alias (`AS day`) in `GROUP BY` and `ORDER BY`.

The pandas version of each clause:

| SQL | pandas |
|---|---|
| `WHERE cond` | `df[mask]` before the `groupby` |
| `GROUP BY key` | `df.groupby(key)` (key can be a column or a computed Series, like a formatted date) |
| `avg(value)`, `count(*)`, `sum(value)` | `.agg(avg_f=("value", "mean"), n=("value", "size"), ...)` |
| `HAVING count(*) < 288` | filter **after** the groupby: `grouped[grouped.n < 288]` |
| `ORDER BY x DESC LIMIT 1` | `.sort_values("x", ascending=False).head(1)` |

So `HAVING` is not a special pandas feature. It's just an ordinary filter on the small table `groupby` gives you.
`WHERE` and `HAVING` differ in SQL only because of clause order; in pandas the order of your statements says it.

**How each engine groups.** pandas **hashes**: one pass over the rows, each row dropped into a bucket for its key,
O(n). SQLite either **sorts** the rows by the key (into a temporary B-tree) and sums runs of equal keys, which is
O(n log n), or, if the rows already come out in key order, skips the sort and streams. The primary key is
`(timeseries_id, ts)`, so grouping by `timeseries_id` needs no sorting, but grouping by an expression of `ts`,
like the day, does. `EXPLAIN QUERY PLAN` says which (below).

## Run

```python
import time

import pandas as pd

import lab

conn = lab.connect()

OAT = "bf422925-1e2d-598d-9069-3b0f17d49c48"  # AHU_1 outside air temp, F
FAN = "9ebf80dd-7821-510b-b2c0-cd0151e093c9"  # AHU_1 supply fan status, 0/1

SERIES_SQL = "SELECT ts, value FROM samples WHERE timeseries_id = :uid"


def series(uid):
    df = lab.query(conn, SERIES_SQL, {"uid": uid})
    dt = pd.to_datetime(df["ts"], unit="s", utc=True)
    return df.assign(day=dt.dt.strftime("%Y-%m-%d"), month=dt.dt.strftime("%Y-%m"))


oat, fan = (
    series(OAT),
    series(FAN),
)  # one series each; day/month are the pandas twins of date()/strftime()
```

**Monthly average outside air temperature.** `groupby` on a column, `agg` for the statistic.

```python
MONTHLY_SQL = """
SELECT strftime('%Y-%m', ts, 'unixepoch') AS month,
       avg(value) AS avg_f
FROM samples
WHERE timeseries_id = :uid
GROUP BY month
ORDER BY month
"""
monthly_sql = lab.query(conn, MONTHLY_SQL, {"uid": OAT})
monthly_pd = oat.groupby("month").agg(avg_f=("value", "mean")).reset_index()
lab.assert_parity(monthly_pd, monthly_sql, keys=["month"], label="monthly average")
print(monthly_sql.round(1).to_string(index=False))
assert len(monthly_sql) == 5  # March to July
assert monthly_sql.iloc[0].month == "2026-03" and round(monthly_sql.iloc[0].avg_f, 1) == 41.5
```

**The hottest day on average.** Group by day, then sort the small result and keep the top row.

```python
HOTDAY_SQL = """
SELECT date(ts, 'unixepoch') AS day, avg(value) AS avg_f
FROM samples
WHERE timeseries_id = :uid
GROUP BY day
ORDER BY avg_f DESC
LIMIT 1
"""
hotday_sql = lab.query(conn, HOTDAY_SQL, {"uid": OAT})
daily_avg = oat.groupby("day").agg(avg_f=("value", "mean")).reset_index()
hotday_pd = daily_avg.sort_values("avg_f", ascending=False).head(1).reset_index(drop=True)
lab.assert_parity(hotday_pd, hotday_sql, label="hottest day")
assert hotday_sql.iloc[0].day == "2026-07-01" and round(hotday_sql.iloc[0].avg_f, 1) == 88.3
```

1 July (88.30) edges out 2 July (88.25) by 0.04 °F, so the two look tied at one decimal. The sort used the
unrounded averages. Round for display only, as in Day 4.

**Days that don't have a full 288 readings.** The condition is on the group's `count(*)`, so it must be `HAVING`.

```python
SHORT_SQL = """
SELECT date(ts, 'unixepoch') AS day, count(*) AS n
FROM samples
WHERE timeseries_id = :uid
GROUP BY day
HAVING count(*) < :full_day
ORDER BY day
"""
short_sql = lab.query(conn, SHORT_SQL, {"uid": OAT, "full_day": 288})
counts = oat.groupby("day").agg(n=("value", "size")).reset_index()
short_pd = counts[counts.n < 288].reset_index(
    drop=True
)  # HAVING = an ordinary filter after the groupby
lab.assert_parity(short_pd, short_sql, keys=["day"], label="short days")
print(short_sql.to_string(index=False))
assert short_sql.day.tolist() == ["2026-03-16", "2026-07-17"]
assert short_sql.n.tolist() == [280, 120]
```

The two short days are the first (2026-03-16, starts at 00:40, 280 readings) and the last (2026-07-17, ends at 09:55,
120 readings). There are no gaps in between. Real historians usually aren't this tidy, so checking is always worth it.

**`WHERE` vs `HAVING`.** A `WHERE` on `value` filters rows *before* counting, so it changes what is counted. Count only
the readings above 90 °F per day, and the days with no such readings vanish, because no rows reach the group:

```python
HOT_COUNT_SQL = """
SELECT date(ts, 'unixepoch') AS day, count(*) AS n_hot
FROM samples
WHERE timeseries_id = :uid AND value > 90      -- row filter, before grouping
GROUP BY day
ORDER BY day
"""
hot_sql = lab.query(conn, HOT_COUNT_SQL, {"uid": OAT})
hot_pd = (
    oat[oat.value > 90].groupby("day").agg(n_hot=("value", "size")).reset_index()
)  # mask, then group
lab.assert_parity(hot_pd, hot_sql, keys=["day"], label="WHERE before GROUP BY")
print(len(hot_sql), "of", counts.shape[0], "days ever passed 90 F")
assert len(hot_sql) < len(counts)
```

**Per series.** Do all 118 series have the same number of readings? This is the one place that needs the whole
table in pandas, so we load just the id column, once.

```python
PER_SERIES_SQL = "SELECT timeseries_id, count(*) AS n FROM samples GROUP BY timeseries_id"

t = time.perf_counter()
per_series_sql = lab.query(conn, PER_SERIES_SQL)
t_sql = time.perf_counter() - t

t = time.perf_counter()
ids = lab.query(conn, "SELECT timeseries_id FROM samples")  # 4.2 million ids, loaded once
per_series_pd = ids.groupby("timeseries_id").agg(n=("timeseries_id", "size")).reset_index()
t_pd = time.perf_counter() - t

lab.assert_parity(
    per_series_pd, per_series_sql, keys=["timeseries_id"], label="readings per series"
)
print(
    f"SQL GROUP BY: {t_sql * 1000:7.0f} ms (118 rows back)   load + groupby: {t_pd * 1000:7.0f} ms"
)
assert (
    per_series_sql.n.nunique() == 1 and per_series_sql.n[0] == 35_536 and len(per_series_sql) == 118
)
del ids  # free the 4.2 million rows
```

One distinct count for everyone: all 118 series have 35,536 readings. The SQL grouped in a single streaming pass
without a sort; pandas first had to pull 4.2 million strings into Python. Same answer, much less data moved.

**How SQLite plans each `GROUP BY`.**

```python
def plan(sql):
    return " | ".join(r[-1] for r in conn.execute("EXPLAIN QUERY PLAN " + sql, {"uid": OAT}))


p_series = plan(PER_SERIES_SQL)
p_day = plan(HOTDAY_SQL)
print(p_series)
print(p_day)
assert "TEMP B-TREE" not in p_series  # already in key order: stream, no sort
assert "TEMP B-TREE" in p_day  # grouping by a function of ts needs a temporary sorted structure
```

## Try it

1. Readings per series: does every one of the 118 series have the same count? (The per-series block above did it
   with `GROUP BY`. Now count how many series share each count, in SQL with a **subquery**: a query in a `FROM`.)
2. Daily run hours of AHU_1's supply fan. Which day ran longest?

<details><summary>Answers</summary>

```python
SAME_COUNT_SQL = """
SELECT n AS readings, count(*) AS series
FROM (SELECT timeseries_id, count(*) AS n FROM samples GROUP BY timeseries_id)
GROUP BY n
"""
same_sql = lab.query(conn, SAME_COUNT_SQL)
same_pd = (
    per_series_pd.groupby("n")
    .size()
    .rename("series")
    .reset_index()
    .rename(columns={"n": "readings"})
)
lab.assert_parity(same_pd, same_sql, keys=["readings"], label="series per count")
assert same_sql.iloc[0].tolist() == [35_536, 118]
assert len(same_sql) == 1

RUN_HOURS_SQL = """
SELECT date(ts, 'unixepoch') AS day, sum(value) * 5 / 60.0 AS run_hours
FROM samples
WHERE timeseries_id = :uid
GROUP BY day
ORDER BY run_hours DESC, day
LIMIT 3
"""
run_sql = lab.query(conn, RUN_HOURS_SQL, {"uid": FAN})
daily_hours = fan.groupby("day").agg(run_hours=("value", lambda v: v.sum() * 5 / 60)).reset_index()
run_pd = (
    daily_hours.sort_values(["run_hours", "day"], ascending=[False, True])
    .head(3)
    .reset_index(drop=True)
)
lab.assert_parity(run_pd, run_sql, keys=["day"], label="longest run days")
print(run_sql.round(1).to_string(index=False))
assert len(run_sql) == 3
assert run_sql.run_hours.iloc[0] == 24.0
```

A query in a `FROM` is a **subquery**: a table made on the fly. In pandas it is just the previous step's result.
One row back means one count for everyone: all 118 series have 35,536 readings.

Several days ran all 24 hours. Is that normal for an office AHU? That's a question for the building's operators,
and it's the kind of finding retro-commissioning starts from.

</details>

## Week 1 challenge

Using only the four UUIDs from Day 2, write **one query** that reports, for each month: the average outside air
temperature, AHU_1's fan run hours, and the number of readings where duct static was above 1.5 inH2O. (Hint: you
can't do it cleanly yet. Try, notice what makes it awkward, and keep the attempt for Day 9.)

As a warm-up, do it in pandas first: three `groupby("month")` calls on three loaded series, then `pd.concat(...,
axis=1)`. That is your oracle. Once Day 9's SQL gives a one-query answer, `lab.assert_parity` the two. Notice
what is easy in pandas (separate frames, glued by the index) and awkward in SQL (one table, one `WHERE`, but
three series).
