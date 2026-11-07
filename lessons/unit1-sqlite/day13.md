# Day 13 — Window functions: LAG, rolling averages, streaks

**Goal:** compare each row with its neighbours in time, without collapsing rows like `GROUP BY` does. SQL window
functions and pandas `shift` / `rolling` / `cumsum` are the same ideas; do each both ways and check they agree.

## Read

A **window function** computes a value for each row from a "window" of related rows. All rows stay in the result.

```
LAG(x)        OVER (PARTITION BY equipment_id ORDER BY ts)   -- x from the previous row
LEAD(x)       OVER (...)                                      -- x from the next row
ROW_NUMBER()  OVER (PARTITION BY ... ORDER BY ts)             -- 1, 2, 3 ... within each partition
AVG(x)        OVER (PARTITION BY ... ORDER BY ts
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) -- rolling mean of the last 12 rows (1 hour)
SUM(x)        OVER (PARTITION BY ... ORDER BY ts)             -- running total
```

- `PARTITION BY equipment_id` keeps AHU_1 and AHU_2 separate. Without it, AHU_2's first row would "follow" AHU_1's
  last.
- `ORDER BY ts` defines what "previous" means.

pandas has a one-to-one map. `PARTITION BY` becomes `groupby`, and `ORDER BY` becomes "the frame is already sorted"
(`lab.history()` returns rows sorted by `(equipment_id, ts)`):

| SQL | pandas |
|---|---|
| `LAG(x) OVER (PARTITION BY e ORDER BY ts)` | `df.groupby("e")["x"].shift()` |
| `LEAD(x) OVER (...)` | `df.groupby("e")["x"].shift(-1)` |
| `AVG(x) OVER (... ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)` | `df.groupby("e")["x"].rolling(12, min_periods=1).mean()` |
| `SUM(x) OVER (PARTITION BY e ORDER BY ts)` | `df.groupby("e")["x"].cumsum()` |
| `ROW_NUMBER() OVER (PARTITION BY e, s ORDER BY ts)` | `df.groupby(["e", "s"]).cumcount() + 1` |
| first row's `LAG` is NULL | first row's `shift()` is NaN |

Two details that bite: `rolling(12)` alone leaves the first 11 rows NaN (it wants a full window), while SQL averages
whatever rows exist, so ask for `min_periods=1` to match. And `shift()` turns an integer column into floats (NaN needs
a float), harmless here.

**Streaks (gaps and islands).** Fault rules need "this condition has been true for N rows in a row". The standard
trick takes three steps, in either language:

1. Mark where the value changes: `CASE WHEN x = LAG(x) OVER w THEN 0 ELSE 1 END AS new_streak`, or
   `x.ne(x.groupby(eq).shift())` in pandas.
2. A running sum of those marks numbers each streak: `SUM(new_streak) OVER w AS streak_id`, or `.cumsum()`.
3. Number the rows inside each streak: `ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ...)`, or `cumcount()`.

A window function can't be used directly in `WHERE`, because windows are computed after filtering. Wrap the query in
a subquery, or a `WITH name AS (...)` common table expression (CTE), and filter outside. (pandas has no such rule:
a column is just a column, so you filter it right away.)

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_history(
    conn
)  # lab_history: wide SI table with an (equipment_id, ts) index (Day 11, Day 12)
h = lab.history(conn)  # the same table as a DataFrame, sorted by (equipment_id, ts)
eq = h["equipment_id"]
```

Units are SI now (Day 11), so duct static pressure is in pascals. **LAG: each reading next to the previous one.**

```python
LAG_SQL = """
SELECT equipment_id, ts, duct_static,
       LAG(duct_static) OVER (PARTITION BY equipment_id ORDER BY ts) AS prev
FROM lab_history
"""
lag_sql = lab.query(conn, LAG_SQL)

prev_static = h.groupby("equipment_id")["duct_static"].shift()
lag_pd = h[["equipment_id", "ts", "duct_static"]].assign(prev=prev_static)
lab.assert_parity(lag_pd, lag_sql, keys=["equipment_id", "ts"], label="LAG(duct_static)")

first = lag_pd[lag_pd.equipment_id == "AHU_1"].head(3)
print(first.assign(t=pd.to_datetime(first.ts, unit="s", utc=True)).to_string(index=False))
assert (
    lag_pd[lag_pd.equipment_id == "AHU_1"].prev.isna().sum() == 1
)  # only the first row has no previous
```

The first row's `prev` is NULL in SQL and NaN in pandas: nothing came before it. The parity check treats the two as
equal, and the second AHU's first row is NULL too, because the window is partitioned.

**Fan starts:** off in the previous row, on in this one.

```python
STARTS_SQL = """
WITH w AS (
  SELECT equipment_id, ts, fan_status,
         LAG(fan_status) OVER (PARTITION BY equipment_id ORDER BY ts) AS prev
  FROM lab_history
)
SELECT equipment_id, count(CASE WHEN fan_status = 1 AND prev = 0 THEN 1 END) AS starts
FROM w
GROUP BY equipment_id
ORDER BY equipment_id
"""
starts_sql = lab.query(conn, STARTS_SQL)

prev_fan = h.groupby("equipment_id")["fan_status"].shift()
starts_pd = ((h.fan_status == 1) & (prev_fan == 0)).groupby(eq).sum().rename("starts").reset_index()
lab.assert_parity(starts_pd, starts_sql, label="fan starts")
print(starts_sql.to_string(index=False))
assert starts_sql.set_index("equipment_id").loc["AHU_1", "starts"] == 123
```

About one start a day for 123 days, as you'd expect for a scheduled AHU. (A NaN or NULL `prev` makes the comparison
false in both languages, so the very first row can never count as a start.)

**Longest continuous run** of each fan, in hours: the streak trick.

```python
RUN_SQL = """
WITH marks AS (
  SELECT equipment_id, ts, fan_status,
         CASE WHEN fan_status = LAG(fan_status) OVER (PARTITION BY equipment_id ORDER BY ts)
              THEN 0 ELSE 1 END AS new_streak
  FROM lab_history
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
)
SELECT equipment_id, max(n) * 5 / 60.0 AS longest_run_h
FROM (SELECT equipment_id, streak_id, count(*) AS n FROM streaks WHERE fan_status = 1
      GROUP BY equipment_id, streak_id)
GROUP BY equipment_id
ORDER BY equipment_id
"""
run_sql = lab.query(conn, RUN_SQL)

new_streak = h.fan_status.ne(h.fan_status.groupby(eq).shift()).astype(
    int
)  # step 1: where it changes
streak_id = new_streak.groupby(eq).cumsum()  # step 2: number the streaks
on = h[h.fan_status == 1].assign(streak_id=streak_id)  # step 3 is just a row count per streak
rows_per_run = on.groupby(["equipment_id", "streak_id"]).size()
run_pd = (
    rows_per_run.groupby("equipment_id").max().mul(5 / 60).rename("longest_run_h").reset_index()
)
lab.assert_parity(run_pd, run_sql, label="longest fan run")
print(run_sql.round(1).to_string(index=False))
assert round(run_sql.set_index("equipment_id").loc["AHU_1", "longest_run_h"], 1) == 109.4
```

109 hours: the fan ran for more than four days straight. For an office AHU that's worth asking about (an override?
a schedule left in occupied?). It's the same question Day 9's unoccupied runtime raised.

**Rolling average:** a 1-hour (12-row) mean of duct static, for every row.

```python
ROLL_SQL = """
SELECT equipment_id, ts,
       AVG(duct_static) OVER (PARTITION BY equipment_id ORDER BY ts
                              ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS static_1h
FROM lab_history
"""
roll_sql = lab.query(conn, ROLL_SQL)

roll = h.groupby("equipment_id")["duct_static"].rolling(12, min_periods=1).mean()
roll_pd = h[["equipment_id", "ts"]].assign(static_1h=roll.reset_index(level=0, drop=True))
lab.assert_parity(roll_pd, roll_sql, keys=["equipment_id", "ts"], label="1 h rolling mean")
```

SQLite keeps a running sum it adds to and subtracts from, while pandas uses its own online update, so the two differ
in the last few bits. That's why `assert_parity` compares with a tolerance, never with `==`.

**Why vectorized?** SQL and pandas both walk the sorted rows once, O(n). The difference between them and a Python
`for` loop is the constant: the loop runs the interpreter 71,072 times, the others run compiled code. This loop does
almost nothing per row, so it is only a few times slower; put real logic in the loop body and the gap grows to 100x.

```python
def lag_loop(equips, values):
    out = [float("nan")] * len(values)
    for i in range(1, len(values)):
        if equips[i] == equips[i - 1]:  # same partition?
            out[i] = values[i - 1]
    return out


loop_prev = lag_loop(eq.tolist(), h.duct_static.tolist())
lab.assert_parity(
    pd.DataFrame({"prev": loop_prev}), pd.DataFrame({"prev": prev_static}), label="loop == shift"
)

t_sql = lab.best_time(lambda: lab.query(conn, LAG_SQL))
t_shift = lab.best_time(lambda: h.groupby("equipment_id")["duct_static"].shift())
t_loop = lab.best_time(lambda: lag_loop(eq.tolist(), h.duct_static.tolist()))
print(
    f"LAG over {len(h):,} rows: SQL {t_sql * 1000:.0f} ms (includes fetching) | "
    f"pandas shift {t_shift * 1000:.1f} ms | python loop {t_loop * 1000:.0f} ms"
)
```

pandas looks far faster than SQL here only because the data is already in memory; the SQL time includes reading the
table and building a DataFrame out of it. Compare like with like: both are the same order of work.

## Try it

1. A 1-hour rolling average of AHU_2's duct static pressure. What's its maximum, in pascals?
2. Count AHU_1 fan **stops** (on, then off). Should it equal the starts? Why might it differ by one?

<details><summary>Answers</summary>

1. Filter the rows to AHU_2 first (the inner query's `WHERE` in SQL, a mask in pandas), then window.

```python
MAX_ROLL_SQL = """
SELECT max(r) AS max_static_1h_pa FROM (
  SELECT AVG(duct_static) OVER (ORDER BY ts ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS r
  FROM lab_history WHERE equipment_id = 'AHU_2'
)
"""
max_sql = lab.query(conn, MAX_ROLL_SQL)
ahu2 = h[h.equipment_id == "AHU_2"]
max_pd = pd.DataFrame(
    {"max_static_1h_pa": [ahu2.duct_static.rolling(12, min_periods=1).mean().max()]}
)
lab.assert_parity(max_pd, max_sql, label="max rolling static, AHU_2")
print(round(max_sql.iloc[0, 0], 1), "Pa")
assert round(max_sql.iloc[0, 0], 1) == 417.3
```

   About 417 Pa (1.675 inH2O, the number this lesson used to print before the history became SI).

2. Same shape as the starts, with the comparison flipped:

```python
STOPS_SQL = """
WITH w AS (
  SELECT fan_status, LAG(fan_status) OVER (ORDER BY ts) AS prev
  FROM lab_history WHERE equipment_id = 'AHU_1'
)
SELECT count(*) AS stops FROM w WHERE fan_status = 0 AND prev = 1
"""
stops_sql = lab.query(conn, STOPS_SQL)
f1 = h.loc[h.equipment_id == "AHU_1", "fan_status"]
stops_pd = pd.DataFrame({"stops": [int(((f1 == 0) & (f1.shift() == 1)).sum())]})
lab.assert_parity(stops_pd, stops_sql, label="AHU_1 fan stops")
assert stops_sql.stops[0] == 122
```

   122 stops against 123 starts. They can differ by one because the data can begin or end in the middle of a run
   (it ends with the fan running).

</details>

## Why it matters

"Condition true for N consecutive rows" is how a fault rule ignores a one-sample blip and reports only persistent
problems. Tomorrow that's the confirmation step of a real rule, written once in SQL and once in pandas, with a parity
check between them.
