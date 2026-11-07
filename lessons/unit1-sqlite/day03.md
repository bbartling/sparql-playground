# Day 3 — Time: epoch seconds, `datetime()`, date ranges

**Goal:** turn `ts` into readable dates, and select a day or a month, in SQL and in pandas.

## Read

`ts` is **Unix epoch seconds**: seconds since 1970-01-01 00:00:00 UTC. `1773621600` is 2026-03-16 00:40 UTC.
Historians store time like this because integers sort fast, compare exactly and have no time zone ambiguity.
Everything in this database is **UTC**.

SQLite's date functions read epoch seconds when you add the `'unixepoch'` modifier. pandas does it with
`pd.to_datetime(..., unit="s", utc=True)`. Here is how the two line up for `1773621600`:

| SQL | pandas (`dt = pd.to_datetime(ts, unit="s", utc=True)`) | Result |
|---|---|---|
| `datetime(ts, 'unixepoch')` | `dt.dt.strftime("%Y-%m-%d %H:%M:%S")` | `2026-03-16 00:40:00` |
| `date(ts, 'unixepoch')` | `dt.dt.strftime("%Y-%m-%d")` | `2026-03-16` |
| `strftime('%H', ts, 'unixepoch')` | `dt.dt.strftime("%H")` or `dt.dt.hour` | `00` (hour) |
| `strftime('%w', ts, 'unixepoch')` | `(dt.dt.dayofweek + 1) % 7` | `1` (day of week, **0 = Sunday** in SQL, 0 = Monday in pandas) |
| `unixepoch('2026-07-01')` | `int(pd.Timestamp("2026-07-01", tz="UTC").timestamp())` | `1782864000` (text → epoch seconds) |

In pandas you get a real datetime column with the whole `.dt` toolbox (`.dt.date`, `.dt.floor("D")`,
`.dt.tz_convert(...)`). SQLite has no date type at all: a "date" there is text (or a number) and the date functions
compute on it row by row.

To select a time range, compare `ts` to epoch numbers. Write the range **half-open**, `start <= ts < end`, so
consecutive days never share a reading.

Don't filter with `date(ts, 'unixepoch') = '2026-07-01'`. It gives the same rows, but SQLite has to compute a date
for every row instead of jumping to the range. The pandas twin of that mistake is converting a whole column to
datetimes just to filter it; comparing the integer column to two numbers is a plain vectorized mask.

Why does the first form let SQLite jump? The primary key is `(timeseries_id, ts)`, so within one series the rows are
sorted by `ts`. `ts >= a AND ts < b` is a **range seek**: find `a` by walking the B-tree from the root, O(log n),
then read the k rows until `b`. Wrapping `ts` in a function hides it from the index, so SQLite falls back to
reading all of the series' rows and testing each. `EXPLAIN QUERY PLAN` shows which one it picked (below).

**Time zones.** Store UTC, convert at the edges. pandas can convert to a named zone (`America/Chicago`) and handle
daylight saving. SQLite can only do `'localtime'`, the *machine's* zone, so a query's answer would change with
whoever runs it. That's another reason to keep zone conversion in pandas or application code.

## Run

```python
import pandas as pd

import lab

conn = lab.connect()

OAT = "bf422925-1e2d-598d-9069-3b0f17d49c48"  # AHU_1 outside air temp, F
oat = lab.query(conn, "SELECT ts, value FROM samples WHERE timeseries_id = :uid", {"uid": OAT})
oat["time_utc"] = pd.to_datetime(oat["ts"], unit="s", utc=True)  # tz-aware datetime64[ns, UTC]
print(oat.dtypes)
```

**The first three readings as dates.** SQL's `datetime()` returns text, so we format the pandas side the same way.

```python
FIRST3_SQL = """
SELECT datetime(ts, 'unixepoch') AS time_utc, value
FROM samples
WHERE timeseries_id = :uid
ORDER BY ts
LIMIT 3
"""
first3_sql = lab.query(conn, FIRST3_SQL, {"uid": OAT})
first3_pd = (
    oat.sort_values("ts")
    .head(3)
    .assign(time_utc=lambda d: d["time_utc"].dt.strftime("%Y-%m-%d %H:%M:%S"))[
        ["time_utc", "value"]
    ]
    .reset_index(drop=True)
)
lab.assert_parity(first3_pd, first3_sql, keys=["time_utc"], label="first 3 as dates")
print(first3_sql)
assert first3_sql.iloc[0].tolist() == ["2026-03-16 00:40:00", 69.0327]
```

**First and last timestamp in the whole database.** Every series covers the same period (Day 5 checks), so one
series is a fair oracle for the whole table. SQL answers over all 4.2 million rows without loading any.

```python
RANGE_SQL = """
SELECT datetime(min(ts), 'unixepoch') AS first_utc, datetime(max(ts), 'unixepoch') AS last_utc FROM samples
"""
range_sql = lab.query(conn, RANGE_SQL)
fmt = "%Y-%m-%d %H:%M:%S"
range_pd = pd.DataFrame(
    {
        "first_utc": [oat.time_utc.min().strftime(fmt)],
        "last_utc": [oat.time_utc.max().strftime(fmt)],
    }
)
lab.assert_parity(range_pd, range_sql, label="first and last timestamp")
print(range_sql.iloc[0].tolist())
assert range_sql.iloc[0].tolist() == ["2026-03-16 00:40:00", "2026-07-17 09:55:00"]
```

**All outside air readings on 1 July 2026 (UTC).** Note the epoch bounds are computed once, by the database in
SQL and by pandas in Python, and compared as plain numbers.

```python
DAY_SQL = """
SELECT count(*) AS n
FROM samples
WHERE timeseries_id = :uid
  AND ts >= unixepoch(:start)
  AND ts <  unixepoch(:end)
"""
day_sql = lab.query(conn, DAY_SQL, {"uid": OAT, "start": "2026-07-01", "end": "2026-07-02"})

start = int(pd.Timestamp("2026-07-01", tz="UTC").timestamp())
end = int(pd.Timestamp("2026-07-02", tz="UTC").timestamp())
assert start == 1782864000
day_pd = pd.DataFrame({"n": [int(((oat.ts >= start) & (oat.ts < end)).sum())]})
lab.assert_parity(day_pd, day_sql, label="readings on 2026-07-01")
assert day_sql.n[0] == 288
```

288 = 24 hours × 12 readings an hour: a full day of 5-minute data.

Mixing naive and time-zone-aware datetimes is the classic pandas time bug, so pandas refuses to compare them:

```python
naive = pd.to_datetime(oat["ts"], unit="s")  # no utc=True: naive datetimes
try:
    naive >= pd.Timestamp("2026-07-01", tz="UTC")
except TypeError as err:
    print("TypeError:", err)
else:
    raise AssertionError("expected a naive/aware comparison to fail")
```

That error is the friendly outcome. Always pass `utc=True` when you convert epoch seconds, and build range bounds with
`tz="UTC"`.

**Which plan does SQLite pick?** `EXPLAIN QUERY PLAN` shows whether the range became an index seek.

```python
RANGE_FILTER = "SELECT count(*) FROM samples WHERE timeseries_id = ? AND ts >= ? AND ts < ?"
FUNCTION_FILTER = (
    "SELECT count(*) FROM samples WHERE timeseries_id = ? AND date(ts, 'unixepoch') = ?"
)


def plan(sql, params):
    return conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()[0][-1]


p_range = plan(RANGE_FILTER, (OAT, start, end))
p_func = plan(FUNCTION_FILTER, (OAT, "2026-07-01"))
print(p_range)
print(p_func)
assert "ts>" in p_range and "ts>" not in p_func  # the range is part of the seek, or it isn't

same_rows = conn.execute(FUNCTION_FILTER, (OAT, "2026-07-01")).fetchone()[0]
assert same_rows == day_sql.n[0]  # identical answer, different amount of work

t_range = lab.best_time(lambda: conn.execute(RANGE_FILTER, (OAT, start, end)).fetchone())
t_func = lab.best_time(lambda: conn.execute(FUNCTION_FILTER, (OAT, "2026-07-01")).fetchone())
print(f"range seek: {t_range * 1e6:8.0f} us   date() on every row: {t_func * 1e6:8.0f} us")
```

Same answer both ways, but the first reads about 288 rows and the second reads all 35,536 of the series and runs
`date()` on each. Across a whole table that gap is the difference between milliseconds and many seconds.

## Try it

1. When was the hottest outside air reading, as a date and time?
2. How many readings does the first day, 2026-03-16, have, and why isn't it 288?
3. Show that hottest reading in `America/Chicago` time. (pandas only: SQLite has no named zones.)

<details><summary>Answers</summary>

```python
HOT_SQL = """
SELECT datetime(ts, 'unixepoch') AS time_utc, value FROM samples
WHERE timeseries_id = :uid
ORDER BY value DESC, ts LIMIT 1
"""
hot_sql = lab.query(conn, HOT_SQL, {"uid": OAT})
hot_pd = (
    oat.sort_values(["value", "ts"], ascending=[False, True])
    .head(1)
    .assign(time_utc=lambda d: d["time_utc"].dt.strftime(fmt))[["time_utc", "value"]]
    .reset_index(drop=True)
)
lab.assert_parity(hot_pd, hot_sql, label="hottest reading")
assert hot_sql.iloc[0].tolist() == ["2026-07-14 21:40:00", 98.8608]

FIRST_DAY_SQL = """
SELECT count(*) AS n FROM samples
WHERE timeseries_id = :uid AND ts >= unixepoch(:start) AND ts < unixepoch(:end)
"""
first_day_sql = lab.query(
    conn, FIRST_DAY_SQL, {"uid": OAT, "start": "2026-03-16", "end": "2026-03-17"}
)
lo = int(pd.Timestamp("2026-03-16", tz="UTC").timestamp())
first_day_pd = pd.DataFrame({"n": [int(((oat.ts >= lo) & (oat.ts < lo + 86_400)).sum())]})
lab.assert_parity(first_day_pd, first_day_sql, label="readings on 2026-03-16")
assert first_day_sql.n[0] == 280

hot_local = oat.loc[oat.value.idxmax(), "time_utc"].tz_convert("America/Chicago")
print(hot_local)  # 2026-07-14 16:40:00-05:00
assert hot_local.hour == 16  # CDT = UTC-5
```

1. 2026-07-14 21:40:00 UTC, 98.86 °F.
2. 280. The data starts at 00:40, not midnight, so the first eight readings of that day were never logged.
3. 16:40 local (UTC-5 in July): 21:40 UTC is mid-afternoon, which is when you'd expect the hottest reading.
   Remember that the database is UTC and the *building* is not, which is why "6 am" shows up elsewhere.

</details>

## Why it matters

Building people think in local time ("the fan should start at 6 am"). Databases should store UTC. Converting at the
edges, and noticing when a "6 am start" shows up at 11:00 UTC, is a daily skill. The RDF model will record the site's
time zone so code doesn't have to guess.
