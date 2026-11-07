# Day 19 — Joining weather: the as-of join

**Goal:** attach the most recent weather reading to every 5-minute AHU row, ignoring readings older than two hours,
in SQL (correlated subquery plus an index) and in pandas (`merge_asof`); see why the three ways to do it scale so
differently; then write a sensor-versus-weather rule on top.

## Read

Some Open-FDD rules need a number the building doesn't measure well: the real outdoor temperature. A sensor on an AHU's
outside-air intake can sit in the sun, in a shaded louver, or be wired wrong. The **`OAT-METEO`** rule compares it with
a weather feed (Open-FDD pulls hourly data from Open-Meteo) and flags a sensor that disagrees with the weather.

The join is awkward because the two series don't share timestamps. The AHU logs every 5 minutes; the weather arrives
hourly and sometimes not at all. You can't `JOIN ... ON h.ts = w.ts`. You want, for each AHU row, **the latest weather
row at or before that time, but only if it is recent enough** (here: no more than 2 hours old; otherwise it is
"stale", and the answer is `NULL`/`NaN`, meaning unknown, not "use whatever's old"). This is an **as-of join**.

**The weather in this lesson is a stand-in.** There is no weather feed in this repo, so we make one honestly:
hourly means of the outside-air temperature, taken from AHU_1's own sensor in synthetic data, plus 0.5 °C of noise
(real weather never matches a sensor exactly), with 12% of the hours deleted and one 6-hour block missing, the way a
feed with failures looks. In production this table is the Open-Meteo feed. Because it is derived from AHU_1, AHU_1
will agree with it; AHU_2 has a 5 °C sensor offset we inject, which the rule should find.

How the join is done in each tool:

| | SQL (SQLite) | pandas | plain Python |
|---|---|---|---|
| Idea | per AHU row, look up the newest weather row `<= ts` | merge two sorted tables in one pass | per AHU row, search the weather list |
| Code | `(SELECT w.ts FROM wx w WHERE w.ts <= h.ts AND w.ts >= h.ts - :tol ORDER BY w.ts DESC LIMIT 1)` | `pd.merge_asof(h, wx, on="ts", direction="backward", tolerance=...)` | `bisect_right(wx_ts, ts) - 1` |
| Stale handling | extra `AND w.ts >= h.ts - :tol` | `tolerance=` argument | `if ts - wx_ts > tol` |

**Complexity.** Let N be AHU rows and M weather rows.

- A *nested loop* with no index: for each of N rows, scan all M weather rows. **O(N·M)**. SQLite does this when there
  is no index on `wx(ts)`; so does a naive Python double loop.
- *With an index* (SQLite) or a sorted list and binary search (Python's `bisect`): each lookup is O(log M), so
  **O(N log M)**.
- `merge_asof` on two *sorted* inputs walks both once: **O(N + M)**. The price: the inputs must be sorted by the key,
  which costs O(N log N) if they aren't.

## Run

```python
import sqlite3
from bisect import bisect_right

import numpy as np
import pandas as pd

import lab

conn = lab.connect()

TOL_S = 2 * 3600  # weather older than this is stale
DIFF_C = 3.0  # sensor-vs-weather disagreement, degrees C
CONFIRM_ROWS = 6  # 6 x 5 min = 30 minutes


def make_weather(df, seed=3):
    """A stand-in weather feed: hourly means of df.oat (+ noise), with some hours missing."""
    rng = np.random.default_rng(seed)
    hour = (df.ts // 3600) * 3600
    wx = df.groupby(hour).oat.mean().rename("wx_oat").reset_index()
    wx["wx_oat"] = (wx.wx_oat + rng.normal(0, 0.5, len(wx))).round(2)
    wx = wx[rng.random(len(wx)) >= 0.12]
    return wx[~wx.index.isin(range(len(wx) // 2, len(wx) // 2 + 6))].reset_index(drop=True)


N = 8_640  # 30 days of 5-minute rows per AHU
ahu = lab.synthetic_history(N, equips=2)
a, b = N // 4, N // 4 + N // 5
bias = (
    (ahu.equipment_id == "AHU_2") & (np.arange(len(ahu)) % N >= a) & (np.arange(len(ahu)) % N < b)
)
ahu.loc[bias, "oat"] += 5.0  # AHU_2's outside-air sensor reads 5 degC high for 6 days
wx = make_weather(ahu[ahu.equipment_id == "AHU_1"])
print(f"{len(ahu):,} AHU rows, {len(wx)} weather rows (of {N * 300 // 3600} hours)")

mem = sqlite3.connect(":memory:")
lab.to_sqlite(ahu, mem, "h", index=["equipment_id", "ts"])
lab.to_sqlite(wx, mem, "wx", index=["ts"])  # indexed
lab.to_sqlite(wx, mem, "wx_plain")  # the same rows, no index
assert len(wx) < N * 300 // 3600
```

**The as-of join in SQL.** The inner query is run once *per AHU row*, which is what makes it "correlated". The weather
value is then looked up by that timestamp.

```python
def join_sql(table="wx"):
    return f"""
SELECT j.equipment_id, j.ts, j.oat, j.fan_status, j.wx_ts, w.wx_oat
FROM (
  SELECT h.equipment_id, h.ts, h.oat, h.fan_status,
         (SELECT w.ts FROM {table} w
          WHERE w.ts <= h.ts AND w.ts >= h.ts - :tol
          ORDER BY w.ts DESC LIMIT 1) AS wx_ts
  FROM h
) j
LEFT JOIN {table} w ON w.ts = j.wx_ts
"""


joined_sql = lab.query(mem, join_sql(), {"tol": TOL_S})
print(joined_sql.head(3).to_string(index=False))
print("rows with no usable weather:", int(joined_sql.wx_ts.isna().sum()))
```

**The same join in pandas.** `merge_asof` needs both sides sorted by the key. Our table has two AHUs interleaved by
time, so we sort by `ts` for the merge and sort back afterwards. We copy `ts` into a `wx_ts` column so we can see
which weather row matched.

```python
def join_pandas(ahu, wx, tol_s=TOL_S):
    left = ahu.sort_values("ts", kind="mergesort")
    right = wx.assign(wx_ts=wx.ts).sort_values("ts")
    out = pd.merge_asof(left, right, on="ts", direction="backward", tolerance=tol_s)
    return out[["equipment_id", "ts", "oat", "fan_status", "wx_ts", "wx_oat"]]


joined_pd = join_pandas(ahu, wx)
lab.assert_parity(joined_pd, joined_sql, keys=["equipment_id", "ts"], label="as-of join")
```

Same rows, same matches, same `NULL`s. (A detail worth knowing: both treat the 2-hour limit as inclusive, so a reading
exactly 7,200 s old still counts. The parity check above would have failed if they disagreed.)

**How the database does it: `EXPLAIN QUERY PLAN`** (Day 12). With the index, each probe is a B-tree range seek;
without it, a full scan of the weather table (plus a temporary sort for the `ORDER BY`) per AHU row. (SQLite also
builds a throwaway "automatic index" for the final `LEFT JOIN` on `wx_plain`, but not for the subquery's range
condition, which is the expensive part.)

```python
for table in ("wx", "wx_plain"):
    plan = lab.query(mem, "EXPLAIN QUERY PLAN " + join_sql(table), {"tol": TOL_S})
    print(table, "->", plan.detail.tolist())
plan_idx = " ".join(lab.query(mem, "EXPLAIN QUERY PLAN " + join_sql("wx"), {"tol": TOL_S}).detail)
plan_plain = " ".join(
    lab.query(mem, "EXPLAIN QUERY PLAN " + join_sql("wx_plain"), {"tol": TOL_S}).detail
)
assert "SEARCH w USING COVERING INDEX wx_idx" in plan_idx and "SCAN w" in plan_plain
```

**Plain Python, two ways.** The nested loop is what SQLite does with no index. The `bisect` version is the same
idea as the index: keep the weather timestamps sorted and binary-search them.

```python
def nested_loop(ts_list, wx_ts_list, tol_s=TOL_S):
    out = []
    for ts in ts_list:
        best = None
        for w in wx_ts_list:  # scans every weather row: O(M) per AHU row
            if w <= ts and (best is None or w > best):
                best = w
        out.append(best if best is not None and ts - best <= tol_s else None)
    return out


def bisect_loop(ts_list, wx_ts_list, tol_s=TOL_S):
    out = []
    for ts in ts_list:
        i = bisect_right(wx_ts_list, ts) - 1  # O(log M); wx_ts_list must be sorted
        out.append(wx_ts_list[i] if i >= 0 and ts - wx_ts_list[i] <= tol_s else None)
    return out


ts_list, wx_ts_list = ahu.ts.tolist(), sorted(wx.ts.tolist())
want = joined_sql.set_index(["equipment_id", "ts"]).wx_ts
key = pd.MultiIndex.from_arrays([ahu.equipment_id, ahu.ts])
for name, fn in (("nested loop", nested_loop), ("bisect", bisect_loop)):
    got = pd.Series(fn(ts_list, wx_ts_list), index=key, dtype="float64")
    lab.assert_parity(
        got.rename("wx_ts").reset_index(),
        want.reset_index(),
        keys=["equipment_id", "ts"],
        label=name,
    )
```

**Timing, growing the data.** One AHU, weather one hour per 12 AHU rows. We stop the two O(N·M) methods at
10,000 rows; at a million rows they would run for hours. `NaN` means "not run".

```python
def timing_case(n):
    d = lab.synthetic_history(n)
    w = make_weather(d)
    m = sqlite3.connect(":memory:")
    lab.to_sqlite(d[["ts"]], m, "h")  # the timing only needs the timestamps
    lab.to_sqlite(w, m, "wx", index=["ts"])
    lab.to_sqlite(w, m, "wx_plain")
    return d, w, m


COUNT_SQL = """
SELECT COUNT(wx_ts) FROM (
  SELECT (SELECT w.ts FROM {t} w WHERE w.ts <= h.ts AND w.ts >= h.ts - :tol ORDER BY w.ts DESC LIMIT 1) AS wx_ts
  FROM h)
"""

rows = []
for n in lab.sizes([1_000, 10_000, 100_000, 1_000_000]):
    d, w, m = timing_case(n)
    reps = 3 if n <= 100_000 else 1
    tl, wl = d.ts.tolist(), sorted(w.ts.tolist())
    wx_frame = w.assign(wx_ts=w.ts)
    expected = int(bisect_loop(tl, wl).count(None))
    row = {"N": n, "M": len(w)}
    cases = {
        "sql_index_s": lambda: m.execute(COUNT_SQL.format(t="wx"), {"tol": TOL_S}).fetchone()[0],
        "bisect_s": lambda: bisect_loop(tl, wl),
        "asof_s": lambda: pd.merge_asof(
            d[["ts"]], wx_frame, on="ts", direction="backward", tolerance=TOL_S
        ),
    }
    if n <= 10_000:  # the O(N*M) methods
        cases["sql_noindex_s"] = lambda: m.execute(
            COUNT_SQL.format(t="wx_plain"), {"tol": TOL_S}
        ).fetchone()[0]
        cases["nested_s"] = lambda: nested_loop(tl, wl)
    for name, fn in cases.items():
        row[name] = lab.best_time(fn, reps)
    matched = int(m.execute(COUNT_SQL.format(t="wx"), {"tol": TOL_S}).fetchone()[0])
    assert matched == n - expected  # SQL and bisect found the same number of matches
    assert matched == int(cases["asof_s"]().wx_oat.notna().sum())  # ... and so did merge_asof
    rows.append(row)
    m.close()
timing = pd.DataFrame(rows)[
    ["N", "M", "nested_s", "sql_noindex_s", "sql_index_s", "bisect_s", "asof_s"]
]
print(timing.to_string(index=False, float_format=lambda x: f"{x:,.4g}"))
```

Read it in three parts. **The unindexed methods** (`nested_s`, `sql_noindex_s`) grow by about 100x for every 10x of
data (N grows 10x and so does M, so N·M grows 100x), which is why they stop at 10,000. SQLite's unindexed
subquery is a compiled nested loop, so it beats the Python nested loop by a constant factor but follows the same
curve. **With an index** (`sql_index_s`, and `bisect_s`, the Python equivalent) the growth is about 10x per 10x: N
lookups, each O(log M). **`merge_asof`** is the quickest because it does the whole job as one O(N + M) merge in compiled
code. It has almost no per-row overhead.

The lesson that carries over to all of Week 4: an index (or a sort) changes the *shape* of the curve. Vectorizing only
changes the slope.

**A sensor-versus-weather rule.** In the spirit of `OAT-METEO`: while the fan runs, flag the AHU when its outdoor
sensor differs from the weather by more than 3 °C, confirmed for 6 rows (30 minutes). No weather (stale or missing)
means *unknown*, so no fault. In SQL, the join result is a CTE under the streak machinery from Day 14.

```python
RULE_SQL = (
    "WITH j AS ("
    + join_sql()
    + """), base AS (
  SELECT equipment_id, ts, wx_oat,
         CASE WHEN fan_status = 1 AND wx_oat IS NOT NULL AND ABS(oat - wx_oat) > :diff THEN 1 ELSE 0 END AS raw_fault
  FROM j
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts) THEN 0 ELSE 1 END
         AS new_streak FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len FROM streaks
)
SELECT equipment_id, ts, wx_oat, raw_fault, streak_id,
       CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
FROM ranked
"""
)
rule_sql = lab.query(mem, RULE_SQL, {"tol": TOL_S, "diff": DIFF_C, "confirm": CONFIRM_ROWS})


def rule_pandas(joined, diff_c=DIFF_C, confirm=CONFIRM_ROWS):
    j = joined.sort_values(["equipment_id", "ts"]).reset_index(drop=True)
    eq = j.equipment_id
    raw = ((j.fan_status == 1) & j.wx_oat.notna() & ((j.oat - j.wx_oat).abs() > diff_c)).astype(int)
    streak = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
    length = raw.groupby([eq, streak]).cumcount() + 1
    fault = ((raw == 1) & (length >= confirm)).astype(int)
    return j[["equipment_id", "ts", "wx_oat"]].assign(raw_fault=raw, streak_id=streak, fault=fault)


rule_pd = rule_pandas(joined_pd)
lab.assert_parity(rule_pd, rule_sql, keys=["equipment_id", "ts"], label="sensor vs weather rule")

hours = rule_sql.groupby("equipment_id").fault.sum() * 5 / 60
print(hours.round(2).to_dict())
assert hours["AHU_2"] > 20 * max(
    hours["AHU_1"], 0.25
)  # the biased sensor is found; the healthy one is quiet
```

AHU_2's offset is found, and AHU_1, which the weather was derived from, stays almost silent. In real data there would be
more false alarms, which is why the rule has a 3 °C tolerance, a confirmation time and a stale-weather guard. Note what
the 2-hour tolerance bought: when the weather feed is down, the rule says nothing, instead of comparing a live sensor
to yesterday's weather.

## Try it

1. Tighten the tolerance to 1 hour. How many AHU rows lose their weather? Check SQL and pandas parity.
2. Replace "latest at or before" with "nearest *after*": SQL `w.ts >= h.ts ... ORDER BY w.ts ASC`, pandas
   `direction="forward"`. When would you ever want that, and when is it a bug?

<details><summary>Answers</summary>

```python
# 1. 1-hour tolerance
sql_1h = lab.query(mem, join_sql(), {"tol": 3600})
pd_1h = join_pandas(ahu, wx, 3600)
lab.assert_parity(pd_1h, sql_1h, keys=["equipment_id", "ts"], label="1 h tolerance")
lost = int(sql_1h.wx_ts.isna().sum()) - int(joined_sql.wx_ts.isna().sum())
print("extra rows without weather:", lost)
assert lost > 0

# 2. forward direction
FORWARD_SQL = (
    join_sql()
    .replace("w.ts <= h.ts AND w.ts >= h.ts - :tol", "w.ts >= h.ts AND w.ts <= h.ts + :tol")
    .replace("ORDER BY w.ts DESC", "ORDER BY w.ts ASC")
)
fwd_sql = lab.query(mem, FORWARD_SQL, {"tol": TOL_S})
left = ahu.sort_values("ts", kind="mergesort")
fwd_pd = pd.merge_asof(left, wx.assign(wx_ts=wx.ts), on="ts", direction="forward", tolerance=TOL_S)[
    ["equipment_id", "ts", "oat", "fan_status", "wx_ts", "wx_oat"]
]
lab.assert_parity(fwd_pd, fwd_sql, keys=["equipment_id", "ts"], label="forward as-of")
assert (fwd_sql.wx_ts.dropna() >= fwd_sql.ts[fwd_sql.wx_ts.notna()]).all()
```

1. Rows lose weather in the hours after a feed outage: with a 1-hour limit, a row whose latest reading is 1-2 hours
   old becomes unknown. The two implementations still agree row for row.
2. The forward join pairs each row with a *future* weather reading. That is legitimate for offline analysis when a value
   is stamped at the *end* of its interval (a mean over the previous hour). It is a **look-ahead bug** in anything that
   claims to run live, or in a backtest of a live rule: the rule would "know" something it couldn't have known yet.
   Always ask which direction is honest for the data you're joining.

</details>

## Why it matters

"Latest value at or before" is the most common join in building data: setpoints that change a few times a day against
readings every minute, schedules against measurements, weather against everything. Remember the three shapes: a nested
loop (O(N·M)), an index lookup (O(N log M)), a sorted merge (O(N + M)). Day 20 pits the three tools against each other on
the FC1 rule at scale.
