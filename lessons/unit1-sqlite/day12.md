# Day 12 — Indexes and `EXPLAIN QUERY PLAN`

**Goal:** see how SQLite finds rows, time the same query with and without an index, and see what pandas does
instead (a scan, or a sorted index).

## Read

A table without a useful index is a list: to find rows, SQLite **scans** all of them, O(n). An **index** is a B-tree
sorted by some columns. Finding a key or a key range is O(log n), then it walks the matching rows in order.

`samples` is `WITHOUT ROWID` with primary key `(timeseries_id, ts)`, so the table **is** a B-tree sorted by series,
then time. That makes some questions cheap and others not:

| Query filters on | Can use the key? |
|---|---|
| `timeseries_id = ?` | yes, it's the first key column |
| `timeseries_id = ? AND ts BETWEEN ...` | yes, both columns, range on the second |
| `ts BETWEEN ...` alone | **no**: time is only sorted *within* each series, so it must scan |
| `date(ts, 'unixepoch') = ...` | the function hides `ts` from the index |

Prefix `EXPLAIN QUERY PLAN` to any query and SQLite tells you its plan instead of running it. Look for
`SEARCH ... USING PRIMARY KEY` / `USING INDEX` (good) vs `SCAN table` (reads everything).

The tradeoff: every index speeds up some reads, but costs disk space and slows every insert. Historians index exactly
what they're queried by (series + time) and little else.

### The same idea in pandas

A DataFrame has no query planner. You choose the algorithm by how you write the line:

| Want | pandas | Cost per lookup |
|---|---|---|
| rows where `equipment_id == 'AHU_1'` and `ts` in a range | boolean mask: `df[(df.equipment_id == "AHU_1") & (df.ts >= a) & (df.ts < b)]` | **O(n)**: compares every row, every time (SQL's `SCAN`) |
| the same, after `set_index(["equipment_id", "ts"]).sort_index()` | `df.loc[("AHU_1", slice(a, b))]` | **O(log n)**: binary search on the sorted index (SQL's `SEARCH USING INDEX`) |
| the same on one sorted array | `np.searchsorted(ts, [a, b])`, then slice | **O(log n)** |

Sorting costs O(n log n) once. After that every lookup is O(log n). That's all a B-tree index is: a sorted copy
you pay for up front. So the question is always the same one: **how many lookups will you do?**

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_history(
    conn
)  # lab_history (Day 11). It comes with an index; we drop it to see the "before".
conn.execute("DROP INDEX IF EXISTS lab_history_eq_ts")
conn.commit()

SID = "bf422925-1e2d-598d-9069-3b0f17d49c48"  # one series (a sensor on AHU_1)
T0 = int(pd.Timestamp("2026-07-01", tz="UTC").timestamp())  # 2026-07-01 00:00 UTC, epoch seconds
T1 = T0 + 86_400  # one day later


def plan(sql: str, params: dict | tuple = ()) -> list[str]:
    """What SQLite would do for this query (the `detail` column of EXPLAIN QUERY PLAN)."""
    return [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params)]


def show(label: str, sql: str, params: dict | tuple = ()) -> None:
    for step in plan(sql, params):
        print(f"{label:<28} {step}")
```

**Querying `samples`.** One series for one day versus every series for one day:

```python
ONE_SERIES_DAY = "SELECT * FROM samples WHERE timeseries_id = :sid AND ts >= :t0 AND ts < :t1"
ALL_SERIES_DAY = "SELECT * FROM samples WHERE ts >= :t0 AND ts < :t1"
p = {"sid": SID, "t0": T0, "t1": T1}
p_ts = {"t0": T0, "t1": T1}

show("one series, one day:", ONE_SERIES_DAY, p)
show("every series, one day:", ALL_SERIES_DAY, p_ts)

n_one = len(conn.execute(ONE_SERIES_DAY, p).fetchall())
n_all = len(conn.execute(ALL_SERIES_DAY, p_ts).fetchall())
print(n_one, "rows vs", n_all, "rows")
assert (n_one, n_all) == (288, 33984)
assert "SEARCH" in plan(ONE_SERIES_DAY, p)[0] and "SCAN" in plan(ALL_SERIES_DAY, p_ts)[0]
```

The first plan is `SEARCH samples USING PRIMARY KEY (timeseries_id=? AND ts>? AND ts<?)`: it jumps straight to 288
rows. The second is `SCAN samples`: all 4.2 million rows, to return 33,984. Time them:

```python
t_seek = lab.best_time(lambda: conn.execute(ONE_SERIES_DAY, p).fetchall())
t_scan = lab.best_time(lambda: conn.execute(ALL_SERIES_DAY, p_ts).fetchall())
print(
    f"seek {t_seek * 1000:.2f} ms   scan {t_scan * 1000:.0f} ms   (scan returns {n_all // n_one}x the rows)"
)
```

The seek touches 288 rows; the scan reads 4.2M. The time gap is mostly that, not cleverness.

**Querying `lab_history`, without and with an index.** Its index is gone, so even one AHU-day scans:

```python
AHU_DAY = "SELECT * FROM lab_history WHERE equipment_id = :eq AND ts >= :t0 AND ts < :t1"
q = {"eq": "AHU_1", "t0": T0, "t1": T1}

show("no index:", AHU_DAY, q)
sql_before = lab.query(conn, AHU_DAY, q)
t_before = lab.best_time(lambda: conn.execute(AHU_DAY, q).fetchall())

import time

t = time.perf_counter()
conn.execute("CREATE INDEX lab_history_eq_ts ON lab_history (equipment_id, ts)")
conn.commit()
t_create = time.perf_counter() - t  # the price of the index, paid once

show("with index:", AHU_DAY, q)
sql_after = lab.query(conn, AHU_DAY, q)
t_after = lab.best_time(lambda: conn.execute(AHU_DAY, q).fetchall())

print(
    f"{len(sql_after)} rows | no index {t_before * 1000:.1f} ms -> index {t_after * 1000:.2f} ms "
    f"| CREATE INDEX took {t_create * 1000:.0f} ms"
)
lab.assert_parity(
    sql_before, sql_after, keys=["equipment_id", "ts"], label="same rows, with and without index"
)
assert len(sql_after) == 288
assert "SCAN" in plan(AHU_DAY, q)[0] or "SEARCH" in plan(AHU_DAY, q)[0]
assert "lab_history_eq_ts" in " ".join(plan(AHU_DAY, q))
```

The plan becomes `SEARCH lab_history USING INDEX lab_history_eq_ts`. Same 288 rows either way: an index changes how
fast you get the answer, never what the answer is. (The parity check proves it. Leave the index in place: Days 13–15
use it.)

**The same question in pandas, three ways.** Load the table once, then filter by mask, by sorted index, and by
binary search on one AHU's timestamps:

```python
h = lab.history(conn)  # all 71,072 rows, sorted by (equipment_id, ts)


def by_mask():
    return h[(h.equipment_id == "AHU_1") & (h.ts >= T0) & (h.ts < T1)]  # O(n) every call


hi = h.set_index(["equipment_id", "ts"]).sort_index()  # O(n log n), once


def by_index():
    return hi.loc[("AHU_1", slice(T0, T1 - 1)), :]  # label slices include both ends, so T1 - 1


ahu1 = h[h.equipment_id == "AHU_1"]
ahu1_ts = ahu1.ts.to_numpy()  # sorted, so binary search works


def by_search():
    lo, hi_ = np.searchsorted(ahu1_ts, [T0, T1])  # first index >= T0, first index >= T1
    return ahu1.iloc[lo:hi_]  # O(log n) to find the bounds, then a slice


for name, fn in [("mask", by_mask), ("sorted index", by_index), ("searchsorted", by_search)]:
    got = fn().reset_index()
    got = got[[c for c in sql_after.columns]]
    lab.assert_parity(got, sql_after, keys=["equipment_id", "ts"], label=f"pandas {name} == SQL")

for name, fn in [("mask", by_mask), ("sorted index", by_index), ("searchsorted", by_search)]:
    print(f"pandas {name:<13} {lab.best_time(fn) * 1000:7.3f} ms")
```

All three return exactly SQLite's 288 rows. The mask is the pandas version of `SCAN`; the other two are the pandas
version of `SEARCH USING INDEX`. (Note that `by_search` built `ahu1` with a mask first. That one-time O(n) filter is
the pandas version of paying for the index up front.)

**Does the gap grow with n?** That's what O(n) versus O(log n) means. Same one-day lookup, on a sorted timestamp
column of growing size (synthetic data, one reading every 5 minutes):

```python
rows = []
for n in lab.sizes([10_000, 100_000, 1_000_000, 4_000_000]):
    ts = lab.synthetic_history(n)["ts"].to_numpy()  # sorted
    a = ts[n // 2]
    b = a + 86_400
    t_mask = lab.best_time(lambda: ts[(ts >= a) & (ts < b)])
    t_bin = lab.best_time(lambda: ts[np.searchsorted(ts, a) : np.searchsorted(ts, b)])
    assert ((ts >= a) & (ts < b)).sum() == np.searchsorted(ts, b) - np.searchsorted(ts, a) == 288
    rows.append({"n": n, "mask_ms": t_mask * 1000, "searchsorted_ms": t_bin * 1000})
print(pd.DataFrame(rows).round(4).to_string(index=False))
```

Read down the `mask_ms` column: ten times the rows, about ten times the time. `searchsorted_ms` barely moves.
Doubling n adds one comparison to a binary search; it doubles a scan.

**When does building the index pay off?** Break-even is `build cost / saving per lookup`:

```python
t_build_pd = lab.best_time(lambda: h.set_index(["equipment_id", "ts"]).sort_index())
save_pd = lab.best_time(by_mask) - lab.best_time(by_index)
save_sql = t_before - t_after
print(
    f"pandas: sort_index {t_build_pd * 1000:.0f} ms, saves {save_pd * 1000:.2f} ms/lookup"
    f" -> pays off after ~{t_build_pd / save_pd:.0f} lookups"
    if save_pd > 0
    else "pandas: no saving at this size"
)
print(
    f"SQLite: CREATE INDEX {t_create * 1000:.0f} ms, saves {save_sql * 1000:.2f} ms/lookup"
    f" -> pays off after ~{t_create / save_sql:.0f} lookups"
    if save_sql > 0
    else "SQLite: no saving"
)
```

A handful of lookups: don't bother, just scan. A dashboard that asks this question thousands of times: build it. An
index also isn't free to keep: every new row must be inserted into the sorted structure too, which is why a historian
that writes constantly keeps only the indexes its queries need.

## Try it

1. Check the plan for Day 3's "bad" filter, `date(ts, 'unixepoch') = '2026-07-01'`, with a `timeseries_id`. Which
   part of the key does it still use? What's the pandas analogue of that mistake?
2. If dashboards often ask "all points at one moment" (`ts = ?` across every row), what index would help, and what
   would it cost? Try it on `lab_history`, in SQL and in pandas.

<details><summary>Answers</summary>

1. Wrapping a column in a function hides it from the index. The key's first column is still usable:

```python
DATE_FILTER = (
    "SELECT * FROM samples WHERE timeseries_id = :sid AND date(ts, 'unixepoch') = '2026-07-01'"
)
show("date() filter:", DATE_FILTER, {"sid": SID})

via_date = lab.query(conn, "SELECT count(*) AS n FROM (" + DATE_FILTER + ")", {"sid": SID})
via_range = lab.query(conn, "SELECT count(*) AS n FROM (" + ONE_SERIES_DAY + ")", p)

s = lab.query(conn, "SELECT ts FROM samples WHERE timeseries_id = :sid", {"sid": SID})
day = pd.to_datetime(s.ts, unit="s", utc=True).dt.strftime("%Y-%m-%d")
via_pandas = pd.DataFrame(
    {"n": [int((day == "2026-07-01").sum())]}
)  # converts all 35,536 rows to datetimes

lab.assert_parity(via_pandas, via_date, label="date() filter, pandas == SQL")
lab.assert_parity(via_range, via_date, label="range filter == date() filter")
assert via_date.n[0] == 288 and len(s) == 35536
```

   `SEARCH samples USING PRIMARY KEY (timeseries_id=?)`. It finds the series fast, then evaluates `date(ts)` on all
   35,536 of its rows instead of 288. Same answer as the range form (parity above), just more work. The pandas
   analogue is converting the whole column to datetimes and comparing strings: O(n) work to answer an O(log n)
   question. Compare `ts` against two numbers instead.

2. An index on `lab_history(ts)`. It costs another sorted copy of the keys (for `samples(ts)` that would be a
   hundred-plus MB) and slows every insert. Timescale solves the "by time" access differently: it splits the table
   into time **chunks** (below).

```python
AT_MOMENT = "SELECT * FROM lab_history WHERE ts = :t"
tt = {"t": T0 + 12 * 3600}  # noon UTC, 2026-07-01
show("ts = ?, no ts index:", AT_MOMENT, tt)
t_noidx = lab.best_time(lambda: conn.execute(AT_MOMENT, tt).fetchall())
conn.execute("CREATE INDEX lab_history_ts ON lab_history (ts)")
show("ts = ?, with ts index:", AT_MOMENT, tt)
t_idx = lab.best_time(lambda: conn.execute(AT_MOMENT, tt).fetchall())
at_sql = lab.query(conn, AT_MOMENT, tt)

by_ts = h.set_index("ts").sort_index()  # a sorted, non-unique index: both AHUs share each timestamp
at_pd = by_ts.loc[[tt["t"]]].reset_index()
at_mask = h[h.ts == tt["t"]].reset_index(drop=True)  # the O(n) alternative

lab.assert_parity(
    at_pd[at_sql.columns], at_sql, keys=["equipment_id", "ts"], label="ts = ?, index == SQL"
)
lab.assert_parity(
    at_mask[at_sql.columns], at_sql, keys=["equipment_id", "ts"], label="ts = ?, mask == SQL"
)
print(f"SQLite {t_noidx * 1000:.1f} ms -> {t_idx * 1000:.3f} ms")
assert len(at_sql) == 2  # one row per AHU
conn.execute("DROP INDEX lab_history_ts")  # keep the lab tidy
conn.commit()
```

</details>

## Why it matters

The same thinking applies to triple stores (week 5). A graph of `(subject, predicate, object)` triples needs several
sorted indexes (SPO, POS, OSP) because SPARQL queries fix different positions. Which index a query can use is the
whole performance story. And it's the same story in pandas: `searchsorted` and `.loc` on a sorted index are what an
index is, and a boolean mask over a big frame is a scan you chose to run.
