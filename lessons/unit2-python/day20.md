# Day 20 — Scaling showdown, and the Week 4 challenge

**Goal:** run Day 14's FC1 confirmation-streak rule as a plain Python state machine, as vectorized pandas and as
SQLite window SQL on data that grows 10x per step; compare the times and how they grow; and decide, with numbers, when
each one is the right tool.

## Read

This is the same rule as Day 14: raw fault = fan running and duct static more than 25 Pa below setpoint; a fault is
**confirmed** once the raw fault has held for 2 consecutive rows. All the rule's cleverness is in "consecutive":
each row's answer depends on the rows before it. That's the part that makes the tools differ.

| | Plain Python | pandas | SQLite |
|---|---|---|---|
| Idea | one pass, a tiny state machine: `streak_len` | column ops: `shift`, `cumsum`, `cumcount` | window functions: `LAG`, `SUM OVER`, `ROW_NUMBER` |
| State | one integer, carried along | none: streak ids are *recomputed* with `cumsum` | none: window frames recompute it |
| Work | 1 pass, interpreter speed | ~5 passes over whole arrays, C speed | sort/partition, several window passes |
| Memory | O(1) (streams from the cursor) | O(n) (needs all rows in arrays) | the database engine's (not in Python) |
| Data starts | in the database | has to be loaded first | where it already is |

A state machine is the natural way to say "count consecutive rows" in a loop, and the awkward way to say it in
column operations (Day 13 needed a trick: compare with the previous row, running-sum the changes). SQL and pandas are
both doing that trick. Whether the trick costs more than the interpreter overhead is what the table below shows.

## Run

```python
import sqlite3

import numpy as np
import pandas as pd

import lab

conn = lab.connect()

TOL_PA = 25.0
CONFIRM = 2  # rows (10 minutes at 5-minute spacing)
```

The three implementations. Each returns two numbers: the count of confirmed fault rows, and the number of episodes
(confirmed streaks). The per-row versions exist so we can check every row, not just the totals.

```python
ROWS_SQL = "SELECT fan_status, duct_static, duct_static_sp FROM h ORDER BY equipment_id, ts"


def loop_rule(conn, keep_rows=False):
    """The state machine: only streak_len survives from one row to the next."""
    streak_len, prev_raw = 0, None
    fault_rows = episodes = 0
    flags = []
    for fan, static, sp in conn.execute(ROWS_SQL):  # streams from the cursor
        raw = 1 if fan == 1 and static < sp - TOL_PA else 0
        streak_len = streak_len + 1 if raw == prev_raw else 1
        prev_raw = raw
        fault = 1 if raw == 1 and streak_len >= CONFIRM else 0
        fault_rows += fault
        episodes += (
            1 if fault and streak_len == CONFIRM else 0
        )  # the row where a streak first confirms
        if keep_rows:
            flags.append(fault)
    return (fault_rows, episodes, flags) if keep_rows else (fault_rows, episodes)


def pandas_rule(h, keep_rows=False):
    """h is sorted by (equipment_id, ts). Day 14's column trick."""
    raw = ((h.fan_status == 1) & (h.duct_static < h.duct_static_sp - TOL_PA)).astype(int)
    eq = h.equipment_id
    streak = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
    length = raw.groupby([eq, streak]).cumcount() + 1
    fault = ((raw == 1) & (length >= CONFIRM)).astype(int)
    episodes = int(((raw == 1) & (length == CONFIRM)).sum())
    return (int(fault.sum()), episodes, fault) if keep_rows else (int(fault.sum()), episodes)


RULE_SQL = """
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END AS raw_fault
  FROM h
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts) THEN 0 ELSE 1 END
         AS new_streak FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len FROM streaks
), per_row AS (
  SELECT equipment_id, ts, streak_id,
         CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
  FROM ranked
)
"""
ROWS_OUT_SQL = RULE_SQL + "SELECT equipment_id, ts, fault FROM per_row"
TOTALS_SQL = (
    RULE_SQL + "SELECT COALESCE(SUM(fault), 0) AS fault_rows, "
    "COUNT(DISTINCT CASE WHEN fault = 1 THEN equipment_id || ':' || streak_id END) AS episodes FROM per_row"
)
PARAMS = {"tol": TOL_PA, "confirm": CONFIRM}


def sql_rule(conn):
    r = lab.query(conn, TOTALS_SQL, PARAMS).iloc[0]
    return int(r.fault_rows), int(r.episodes)


def make(n, equips=1):
    df = lab.synthetic_history(n, equips=equips)
    mem = sqlite3.connect(":memory:")
    lab.to_sqlite(df, mem, "h", index=["equipment_id", "ts"])
    return df, mem
```

**Parity first, row by row**, on a small table with two AHUs (so the `PARTITION BY` matters):

```python
df, mem = make(5_000, equips=2)
n_fault, n_eps, flags_loop = loop_rule(mem, keep_rows=True)
_, _, flags_pd = pandas_rule(df, keep_rows=True)
rows_sql = lab.query(mem, ROWS_OUT_SQL, PARAMS)

out_loop = df[["equipment_id", "ts"]].assign(fault=flags_loop)
out_pd = df[["equipment_id", "ts"]].assign(fault=flags_pd)
lab.assert_parity(out_pd, rows_sql, keys=["equipment_id", "ts"], label="pandas vs SQL, per row")
lab.assert_parity(out_loop, rows_sql, keys=["equipment_id", "ts"], label="loop vs SQL, per row")
print("totals:", loop_rule(mem), pandas_rule(df), sql_rule(mem))
assert loop_rule(mem) == pandas_rule(df) == sql_rule(mem)
assert n_fault > 0 and n_eps > 0
```

Two things to notice in that check. First, `streak_id` restarts at 1 for each AHU (the window is partitioned), so
counting episodes across AHUs needs `DISTINCT equipment_id || ':' || streak_id`; counting plain `streak_id` merges
different AHUs' episodes into one. Second: the loop above, written for one stream, gave the right answer for two AHUs only
because `ORDER BY equipment_id, ts` puts each AHU's rows in a block and the weak-fan window is in the middle of each
(the loop would carry a streak from the end of AHU_1 into the start of AHU_2 otherwise). A real loop needs the same reset
logic `PARTITION BY` gives SQL for free (Day 18's loop has it). For the timing below we use one AHU.

**The showdown.** Synthetic data, 10x more rows each step. For pandas we report two numbers: the computation on a
DataFrame already in memory, and "load from SQLite, then compute" (that's the fair comparison if the data lives in the
database). Parity of the totals is checked at every size.

```python
rows = []
for n in lab.sizes([1_000, 10_000, 100_000, 1_000_000]):
    df_n, mem_n = make(n)
    reps = 3 if n <= 100_000 else 1
    totals = (loop_rule(mem_n), pandas_rule(df_n), sql_rule(mem_n))
    assert totals[0] == totals[1] == totals[2], (n, totals)  # parity at every size
    rows.append(
        {
            "rows": n,
            "loop": lab.best_time(lambda: loop_rule(mem_n), reps),
            "pandas": lab.best_time(lambda: pandas_rule(df_n), reps),
            "load+pandas": lab.best_time(
                lambda: pandas_rule(
                    pd.read_sql_query("SELECT * FROM h ORDER BY equipment_id, ts", mem_n)
                ),
                reps,
            ),
            "sql": lab.best_time(lambda: sql_rule(mem_n), reps),
        }
    )
    mem_n.close()
t = pd.DataFrame(rows).set_index("rows")
print("seconds")
print(t.map(lambda x: f"{x:,.4g}").to_string())
growth = (t / t.shift(1)).dropna()
print("\ngrowth: time at this size / time at the previous (10x smaller) size")
print(growth.round(1).to_string())
```

How to read the growth table: a column of about 10 means O(n): ten times the data, ten times the time. Smaller than 10
at the first rows means fixed overhead (starting a query, allocating arrays) is still a big part of the time. Bigger
than 10 would mean worse than linear: sorting adds a log factor, and once arrays stop fitting in CPU cache each pass
slows down.

```python
big = t.iloc[-1]
print(big.round(3).to_dict())
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert big["loop"] > big["pandas"]  # in-memory column math beats the interpreter loop...
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert big["sql"] > big["pandas"]  # ...and beats window SQL, if the data is already a DataFrame
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert big["load+pandas"] > big["pandas"]  # but loading is a real cost
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert (
        big["loop"] < big["load+pandas"] and big["loop"] < big["sql"]
    )  # from the database, streaming wins here
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert (growth.loc[growth.index[-1]] < 25).all()  # nothing blew up: all roughly linear
```

On the machine this was written on, at a million rows (seconds): pandas on resident data 0.44, the streaming
Python loop 1.4, load-then-pandas 3.6, window SQL 6.4. Two readings of the same table:

- *If the data is already a DataFrame*, pandas wins by about 3x over the loop. The loop's penalty is smaller than on
  Day 16's trivial counting because a state machine is *one* pass, while the pandas version needs several full-array
  passes (`shift`, `ne`, `cumsum`, `groupby.cumcount`).
- *If the data lives in the database*, the honest pandas number is "load, then compute", and that is slower than just
  streaming the rows through a loop. Window SQL is slowest of all here: SQLite sorts the rows, then makes four window
  passes, each of which materializes intermediate rows. SQL's strength is not this kind of row-to-row logic. It
  is the *selective* query that the index answers without reading most of the table (Day 12).

**So when does each one win?**

- **SQL** when the data already lives in the database and you want a small answer: a total, a top-10, one
  AHU's last week. The index finds the rows without reading the rest (Day 12), nothing is copied into Python, and the
  result is one small table. Also when many people or programs need the same logic: the query ships with the data.
  It loses on cost-per-row for complicated row-to-row logic, and it is awkward to step through.
- **pandas** for in-memory column math and exploratory work: it is the fastest once the data is in arrays, and
  the interactive loop (change a line, look at a plot) is why it's the oracle in Open-FDD's parity tests. It loses
  when the data doesn't fit in memory, or when moving the data in costs more than the calculation (Day 16).
- **A plain loop** when the data streams past once and the state is complicated or the data is small: it needs O(1)
  memory (Day 17), it can **stop early** (try it below), and a state machine with ten fields is easier to read than
  ten window functions. Its per-row cost is high, but it is flat. If a loop is the right *shape* and merely slow, tools
  like numba or Cython compile exactly this kind of loop to machine code; that's a story for another course.

Open-FDD ships the pandas version as the reference and the SQL version where the data lives. Both are correct, and the
parity test is what lets you pick per situation.

## Try it

**Stop early.** How long does each version take to find the *first* confirmed fault timestamp in a 1,000,000-row
table (100,000 under quick mode)? Compare the streaming loop that returns at the first hit with the loop that reads
everything. Check that it gets the same timestamp as pandas.

<details><summary>Answer</summary>

```python
n = 100_000 if lab.QUICK else 1_000_000
df_n, mem_n = make(n)


def first_fault_loop(conn):
    streak_len, prev_raw = 0, None
    for fan, static, sp, ts in conn.execute(
        "SELECT fan_status, duct_static, duct_static_sp, ts FROM h ORDER BY equipment_id, ts"
    ):
        raw = 1 if fan == 1 and static < sp - TOL_PA else 0
        streak_len = streak_len + 1 if raw == prev_raw else 1
        prev_raw = raw
        if raw == 1 and streak_len >= CONFIRM:
            return ts  # early exit: the rest of the table is never read
    return None


def first_fault_pandas(h):
    *_, fault = pandas_rule(h, keep_rows=True)
    return int(h.ts[fault == 1].iloc[0])


assert first_fault_loop(mem_n) == first_fault_pandas(df_n)
t_early = lab.best_time(lambda: first_fault_loop(mem_n))
t_full = lab.best_time(lambda: loop_rule(mem_n))
t_pd = lab.best_time(lambda: first_fault_pandas(df_n))
print(f"loop with early exit {t_early:.3f} s, full loop {t_full:.3f} s, pandas {t_pd:.3f} s")
assert t_early < t_full * 0.7
```

The early-exit loop does a fraction of the work (and `ORDER BY equipment_id, ts` matters: it matches the index, so SQLite
streams rows in order instead of sorting a million of them first), because the first confirmed fault is early in the table (the weak
fan window starts a third of the way in, and before that an occasional noise streak trips it). pandas and the window
SQL have no equivalent: they compute every row's state before you can ask for the first. A `LIMIT 1` on the SQL
doesn't help for the same reason. Early exit is the loop's unique strength: here it takes the loop from 1.3 s to 0.5 s, and it would matter far more if
the first fault were near the start or each row cost a network call. (pandas, with everything in memory, can still be
faster in raw time; the loop's win is in *not needing the rest of the data at all*.)

</details>

## Week 4 challenge

Find the **longest confirmed fault episode** for each AHU: its length in rows and in minutes, on a table with two AHUs
of 20,000 rows each (5,000 under quick mode). An episode is a maximal run of consecutive raw-fault rows
that lasts at least `CONFIRM` rows. Implement it three ways (a streaming loop that tracks the current and best run, a
pandas `groupby` on the streak id, and SQL `GROUP BY` the streak id), check parity of all three, and say which one you
would ship if the data were (a) one building's database, (b) a notebook of a month of data, (c) a stream on a controller.

<details><summary>Answer</summary>

```python
n = 5_000 if lab.QUICK else 20_000
df2, mem2 = make(n, equips=2)

# (a) streaming loop: per-equipment state, reset whenever the equipment changes
best = {}
cur_eq = prev_raw = None
run = 0
for eq, fan, static, sp in mem2.execute(
    "SELECT equipment_id, fan_status, duct_static, duct_static_sp FROM h ORDER BY equipment_id, ts"
):
    raw = 1 if fan == 1 and static < sp - TOL_PA else 0
    if eq != cur_eq:
        cur_eq, prev_raw, run = eq, None, 0
        best.setdefault(eq, 0)
    run = run + 1 if raw == prev_raw else 1
    prev_raw = raw
    if raw == 1 and run >= CONFIRM:
        best[eq] = max(best[eq], run)
loop_df = pd.DataFrame({"equipment_id": list(best), "longest_rows": list(best.values())})
loop_df["longest_min"] = loop_df.longest_rows * 5.0

# (b) pandas: size of each raw-fault streak, keep those that confirm, take the max per AHU
raw = ((df2.fan_status == 1) & (df2.duct_static < df2.duct_static_sp - TOL_PA)).astype(int)
eq = df2.equipment_id
streak = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
sizes = raw.groupby([eq, streak]).agg(["first", "size"])
ep = sizes[(sizes["first"] == 1) & (sizes["size"] >= CONFIRM)]["size"]
pd_df = ep.groupby("equipment_id").max().rename("longest_rows").reset_index()
pd_df["longest_min"] = pd_df.longest_rows * 5.0

# (c) SQL: GROUP BY the streak id, filter, then MAX
LONGEST_SQL = """
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END AS raw_fault
  FROM h
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts) THEN 0 ELSE 1 END
         AS new_streak FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), episodes AS (
  SELECT equipment_id, streak_id, COUNT(*) AS rows_in_streak
  FROM streaks WHERE raw_fault = 1 GROUP BY equipment_id, streak_id HAVING COUNT(*) >= :confirm
)
SELECT equipment_id, MAX(rows_in_streak) AS longest_rows, MAX(rows_in_streak) * 5.0 AS longest_min
FROM episodes GROUP BY equipment_id
"""
sql_df = lab.query(mem2, LONGEST_SQL, PARAMS)
print(sql_df.to_string(index=False))

lab.assert_parity(pd_df, sql_df, keys=["equipment_id"], label="longest episode, pandas vs SQL")
lab.assert_parity(loop_df, sql_df, keys=["equipment_id"], label="longest episode, loop vs SQL")
assert (sql_df.longest_rows >= CONFIRM).all() and len(sql_df) == 2
```

Which to ship: (a) one building's database: **SQL**, next to the data, with an index, returning two numbers.
(b) a notebook with a month of data: **pandas**, because you'll want to plot the episodes next. (c) a stream on a
controller: the **loop**, with O(1) memory and early updates the moment each episode ends. All three give the same
answer, which is the point of having the parity check.

</details>

Week 4 in one sentence: the answer is the same everywhere, and *where the data is, how much of it you hold in memory,
and what shape the logic has* decide which tool gets there cheapest.
