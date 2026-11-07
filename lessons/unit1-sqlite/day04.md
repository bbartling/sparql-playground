# Day 4 — Summary stats: COUNT, MIN, MAX, AVG, SUM

**Goal:** summarize a sensor in one row, in SQL and in pandas, and turn a status point into run hours.

## Read

**Aggregate functions** fold many rows into one value. pandas has a method for each:

| SQL | pandas (on a column `v`) | Notes |
|---|---|---|
| `count(*)` | `len(df)` | rows |
| `count(value)` | `v.count()` | rows where `value` is not NULL / NaN |
| `min(value)`, `max(value)` | `v.min()`, `v.max()` | ignore NULLs / NaN |
| `avg(value)` | `v.mean()` | mean of the non-NULL values |
| `sum(value)` | `v.sum()` | total (SQL: NULL for no rows; pandas: 0) |
| `round(x, n)` | `round(x, n)` | for reading, not storage. **Never round before comparing** |

Without `GROUP BY` (tomorrow), an aggregate query returns exactly one row.

A useful trick: a status point is 1 when running and 0 when off. With one reading every 5 minutes,
`sum(status) × 5 / 60` is the **run hours**. Use `60.0`, not `60`: integer division in SQL drops the remainder.
(In Python 3, `/` is always true division, so pandas has no such trap. Different engines, different gotchas.)

**How each engine does it.** Both are one pass over the rows, O(k) for k rows. SQLite computes every aggregate in
the `SELECT` list in the *same* pass, while it streams the rows off the B-tree, and returns a single row. pandas
works on a column in memory: each of `min`, `max`, `mean` is its own fast, vectorized (compiled C loop) pass, and
the rows had to be loaded into Python first. So SQL moves one row of results; pandas moves k rows of input.
Pushing the aggregate into SQL is cheaper whenever you only need the summary, as the timing below shows.

## Run

```python
import sqlite3

import numpy as np
import pandas as pd

import lab

conn = lab.connect()

OAT = "bf422925-1e2d-598d-9069-3b0f17d49c48"  # AHU_1 outside air temp, F
FAN = "9ebf80dd-7821-510b-b2c0-cd0151e093c9"  # AHU_1 supply fan status, 0/1
STATIC = "52422584-9894-50bd-9696-2fbb8b062518"  # AHU_1 duct static pressure, inH2O
STATIC_SP = "761c2b61-4982-5157-bc66-2010cf6e2a47"  # AHU_1 duct static pressure setpoint, inH2O

SERIES_SQL = "SELECT ts, value FROM samples WHERE timeseries_id = :uid"


def series(uid):
    return lab.query(conn, SERIES_SQL, {"uid": uid})


oat, fan, static, static_sp = (series(u) for u in (OAT, FAN, STATIC, STATIC_SP))
```

**AHU_1 outside air temperature, whole dataset.** SQL computes the four statistics unrounded, in one pass.

```python
SUMMARY_SQL = """
SELECT count(*)   AS n,
       min(value) AS min_f,
       max(value) AS max_f,
       avg(value) AS avg_f
FROM samples
WHERE timeseries_id = :uid
"""
summary_sql = lab.query(conn, SUMMARY_SQL, {"uid": OAT})
v = oat["value"]
summary_pd = pd.DataFrame(
    {"n": [len(oat)], "min_f": [v.min()], "max_f": [v.max()], "avg_f": [v.mean()]}
)
lab.assert_parity(
    summary_pd, summary_sql, label="OAT summary"
)  # unrounded: compare the real numbers

shown = summary_sql.iloc[0]
print(
    summary_sql.round({"min_f": 2, "max_f": 2, "avg_f": 3}).to_dict("records")[0]
)  # round only to print
assert (int(shown.n), round(shown.min_f, 2), round(shown.max_f, 2), round(shown.avg_f, 3)) == (
    35536,
    17.83,
    98.86,
    61.276,
)
```

**The same for one day.** Add a half-open range in `ts` to the `WHERE` (Day 3); in pandas it's a mask first.

```python
DAY_SQL = """
SELECT min(value) AS min_f, max(value) AS max_f, avg(value) AS avg_f
FROM samples
WHERE timeseries_id = :uid
  AND ts >= unixepoch(:start) AND ts < unixepoch(:end)
"""
day_sql = lab.query(conn, DAY_SQL, {"uid": OAT, "start": "2026-07-01", "end": "2026-07-02"})
lo = int(pd.Timestamp("2026-07-01", tz="UTC").timestamp())
day = oat[(oat.ts >= lo) & (oat.ts < lo + 86_400)]["value"]
day_pd = pd.DataFrame({"min_f": [day.min()], "max_f": [day.max()], "avg_f": [day.mean()]})
lab.assert_parity(day_pd, day_sql, label="OAT on 2026-07-01")
assert day_sql.iloc[0].round(1).tolist() == [79.9, 97.1, 88.3]
```

**AHU_1 supply fan run hours.** The status is 0/1, so its sum is the number of readings with the fan on.

```python
HOURS_SQL = "SELECT sum(value) * 5 / 60.0 AS run_hours FROM samples WHERE timeseries_id = :uid"
hours_sql = lab.query(conn, HOURS_SQL, {"uid": FAN})
hours_pd = pd.DataFrame({"run_hours": [fan["value"].sum() * 5 / 60]})
lab.assert_parity(hours_pd, hours_sql, label="fan run hours")
print(hours_sql.run_hours[0])
assert round(hours_sql.run_hours[0], 1) == 1574.4
```

The dataset covers about 2,961 hours (35,536 readings × 5 minutes), so the fan ran a bit over half the time.

**NULLs and integer division.** The real series have no NULLs, so here is a three-row table in a throwaway
in-memory database, to see both engines skip them the same way and to see the `60` vs `60.0` trap.

```python
mem = sqlite3.connect(":memory:")
mem.execute("CREATE TABLE t (value REAL)")
mem.executemany("INSERT INTO t VALUES (?)", [(1.0,), (None,), (3.0,)])
null_sql = pd.read_sql_query(
    "SELECT count(*) AS n_rows, count(value) AS n_values, avg(value) AS mean FROM t", mem
)
t = pd.Series([1.0, np.nan, 3.0])
null_pd = pd.DataFrame({"n_rows": [len(t)], "n_values": [t.count()], "mean": [t.mean()]})
lab.assert_parity(
    null_pd, null_sql, label="NULL / NaN handling"
)  # 3 rows, 2 values, mean 2.0 not 4/3

print(mem.execute("SELECT 7 * 5 / 60, 7 * 5 / 60.0").fetchone())  # (0, 0.5833...)
assert mem.execute("SELECT 7 * 5 / 60").fetchone()[0] == 0
```

**Where the time goes.** The summary you want is a single number. Compare asking SQL for it with loading the series
into pandas first and calling `.mean()`:

```python
AVG_SQL = "SELECT avg(value) FROM samples WHERE timeseries_id = ?"
t_sql = lab.best_time(lambda: conn.execute(AVG_SQL, (STATIC,)).fetchone()[0])
t_load_mean = lab.best_time(lambda: lab.query(conn, SERIES_SQL, {"uid": STATIC})["value"].mean())
t_mean_only = lab.best_time(lambda: static["value"].mean())  # series already in memory
print(f"SQL avg(), one row back:         {t_sql * 1000:7.2f} ms")
print(f"load series, then .mean():       {t_load_mean * 1000:7.2f} ms")
print(f"  .mean() alone (already loaded): {t_mean_only * 1000:7.2f} ms")
assert abs(conn.execute(AVG_SQL, (STATIC,)).fetchone()[0] - static["value"].mean()) < 1e-9
```

The `.mean()` itself is a few tenths of a millisecond; vectorized pandas is fast. Nearly all of the pandas cost is
**getting the rows into Python**. If you will ask many questions of the same series, load it once (as this lesson
does) and the load amortises. If you only need one summary of a large table, let SQL do it and move one row.

## Try it

1. What are the average duct static pressure and its average setpoint on AHU_1? Which is bigger?
2. What fraction of the time was AHU_1's fan running? (Hint: the average of a 0/1 column is the fraction.)

<details><summary>Answers</summary>

```python
AVG_ONE_SQL = "SELECT avg(value) AS avg_value FROM samples WHERE timeseries_id = :uid"
for name, uid, frame, want in [
    ("static", STATIC, static, 0.783),
    ("static setpoint", STATIC_SP, static_sp, 1.366),
    ("fan running fraction", FAN, fan, 0.532),
]:
    sql = lab.query(conn, AVG_ONE_SQL, {"uid": uid})
    pdf = pd.DataFrame({"avg_value": [frame["value"].mean()]})
    lab.assert_parity(pdf, sql, label=name)
    assert round(sql.avg_value[0], 3) == want, (name, sql.avg_value[0])
    print(f"{name}: {sql.avg_value[0]:.3f}")
```

The average static (0.78) is far below the average setpoint (1.37). But that includes all the hours the fan was
off, when static is near zero. Day 8 asks the fair question: what is static *while the fan runs*. The fan ran
53.2% of the time, which matches the 1,574 run hours out of about 2,961.

</details>

## Why it matters

Averages over everything hide what matters. A sensor reading 0 °F because the unit is off pulls the average down
just like a cold day does. Most of fault detection is asking "the average **of what, when**?" That's filtering
(Days 8–9) and gating (week 3).
