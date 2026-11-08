# Day 16 — One answer three ways: a Python loop, pandas and SQL

**Goal:** compute the same fault count and run hours with a row-by-row Python loop, with vectorized pandas and with
one SQL aggregate; see that they agree; then measure how each one grows with the data, and what moving the data costs.

## Read

Week 4 asks one question over and over: *the answer is the same, so which tool should compute it?* You have written
Open-FDD-style rules in SQL (Unit 1) and in pandas (Day 14). Plain Python is the third option, and the one a CS
course starts with.

Today's job is deliberately small, so the three versions fit on a screen. Take the FC1 raw condition from Day 14
(**fan running and duct static more than 25 Pa below setpoint**) and compute two numbers:

- `fault_rows`: how many 5-minute rows meet the condition;
- `run_hours`: fan run hours, which is rows with `fan_status = 1` times 5 minutes.

The data is **synthetic** this week, so we can make it as big as we like. `lab.synthetic_history(n)` builds `n` rows
of one AHU in SI units (a daily fan schedule, duct static tracking its setpoint with noise, one weak-fan window), and
it is deterministic: both scripts get identical rows. The SQL script loads them into an in-memory SQLite table
first. That load is **setup**, timed on its own; the computation is what we compare.

How each one does it:

| | Plain Python (in `day16_pandas.py`) | pandas (`day16_pandas.py`) | SQL (`day16_sql.py`) |
|---|---|---|---|
| Where the rows live | Python objects pulled out of a column | DataFrame columns (NumPy arrays) | table in the database |
| Who runs the loop | the interpreter, once per row | compiled C inside NumPy | compiled C inside SQLite |
| Condition | `if fan == 1 and static < sp - tol` | `(fan == 1) & (static < sp - tol)` | `CASE WHEN ... THEN 1 ELSE 0 END` |
| Add them up | `fault_rows += 1` | `mask.sum()` | `SUM(...)` |

**Big-O.** All three are O(n): they touch every row once, so ten times the rows costs about ten times the time. Big-O
hides the **constant factor**, and the constant is what you actually wait for. A Python loop pays interpreter
overhead on every row: fetch a value, compare, update a counter. NumPy and SQLite run the same logic in compiled
loops, so their per-row cost is smaller by one to two orders of magnitude. Same curve, very different slope.

**The hidden cost: moving data.** The pandas and SQL numbers assume the data is already where that tool wants it:
in a DataFrame, or in a table. If your data lives in SQLite and you want pandas, you first pay to copy it into a
DataFrame (`read_sql_query`). If it lives in a DataFrame and you want SQL, you pay to insert it (`to_sql`). Those
copies are O(n) too, and they are usually *bigger* than the computation they enable. Each script times the move it can
see: the pandas script, DataFrame into SQLite; the SQL script, table out into a DataFrame.

## Run

```bash
uv run python lessons/course.py run 16
```

That runs [`day16_pandas.py`](day16_pandas.py), then [`day16_sql.py`](day16_sql.py) (about 20 seconds in all; the
million-row steps dominate). Each is sectioned with numbered comments. The pandas script has version (a), a plain
Python loop, and version (b), vectorized pandas:

```python
def loop_answer(d):
    fault_rows = run_rows = 0
    for fan, static, sp in zip(d["fan_status"], d["duct_static"], d["duct_static_sp"], strict=True):
        if fan == 1:
            run_rows += 1
            if static < sp - TOL_PA:
                fault_rows += 1
    return {"fault_rows": fault_rows, "run_hours": run_rows * STEP_H}


def pandas_answer(d):
    running = d["fan_status"] == 1
    fault = running & (d["duct_static"] < d["duct_static_sp"] - TOL_PA)
    return {"fault_rows": int(fault.sum()), "run_hours": float(running.sum()) * STEP_H}
```

The SQL script is version (c): the loop moves inside the database and one row comes back.

```sql
SELECT SUM(CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END) AS fault_rows,
       SUM(fan_status = 1) * :step_h AS run_hours
FROM h
```

`SUM(fan_status = 1)` works because SQLite comparisons evaluate to 0 or 1. Both scripts print the same answer, for
20,000 rows and then for every benchmark size (`fault_run` and `fault_by_size` in `RESULTS`):

```
 fault_rows  run_hours
       1015    832.667
   rows  fault_rows  run_hours
   1000          73     41.333
  10000         486    419.333
 100000        4993   4164.000
1000000       50412  41664.000
```

The pandas script also prints `loop and pandas agree: True`; the unit test checks pandas against SQL.

**Timing, growing the data.** `lab.best_time` runs a function a few times and keeps the fastest, which hides noise
from whatever else your computer is doing. The data is built once per size, outside the timers. Timings are
**printed, never compared**: they differ on every machine and every run. On the machine this was written on:

```
   rows    loop_s  pandas_s  loop/pandas        (day16_pandas.py)
   1000 0.0002465  0.000226        1.091
  10000  0.002491 0.0003914        6.365
 100000   0.03065 0.0007246         42.3
1000000    0.3069   0.00555         55.3

   rows   load_s  sql_agg_s  read_sql_s  read_sql/agg        (day16_sql.py)
   1000 0.003805  0.0001054    0.001937         18.38
  10000  0.02204   0.001037     0.01824         17.58
 100000   0.2252    0.01153      0.1913         16.58
1000000    2.212      0.123       2.517         20.47
```

Read the tables in two directions. Down a column, the time grows about 10x per row once the data is big enough to
matter: that's O(n). (The smallest sizes are dominated by fixed overhead: starting a query, allocating arrays.) Across
a row, the three tools differ by a constant factor. At a million rows the loop took 0.31 s, the SQL aggregate 0.12 s
(about 2.5x faster than the loop) and pandas 0.0055 s (about 55x faster). Both pandas and SQLite are compiled loops, but
pandas only has to compare and add whole arrays in memory, while SQLite evaluates a `CASE` expression per row,
decoding each row from its B-tree pages as it goes.

**What did it cost to get the data there?** Now the part that surprises people. The pandas script also prints what
it costs to insert the DataFrame into SQLite, next to the pandas computation:

```
   rows  to_sql_s  pandas_calc_s  to_sql/calc
1000000     2.031        0.00555          366
```

And the SQL script's `read_sql_s` column above is the opposite move (SQLite table out into a DataFrame, no
computation at all): 2.5 s at a million rows, about 20 times the SQL aggregate that answers the question in place.
Moving data costs two to three orders of magnitude more than the pandas arithmetic, in either direction: inserting a
DataFrame builds a B-tree and an index entry per row, and reading a table out builds a Python tuple per row before
converting to arrays. If the data lives in SQLite and you need *one number*, "load into pandas, then compute"
(`read_sql_s` plus the pandas time) loses badly to the SQL aggregate, because the aggregate runs where the data is
and only one row crosses the boundary. "pandas is faster than SQL" is only true *once the data is already a
DataFrame*. If you will ask fifty questions of the same data, pay the load once and use pandas. That trade-off is
Day 20's main theme.

The worst version of all is the one that looks innocent: loop in Python, but over a list you built with `fetchall()`.
You pay the transfer *and* the interpreter, and hold every row in memory as well. Day 17 measures that memory.

## Try it

1. The loop above reads three columns. What happens to its time if it reads all six (iterating
   `d.itertuples(index=False, name=None)`)? Time it at 100,000 rows and say why.
2. Add a third number to all three versions: the *fault run hours*, `fault_rows * 5 / 60`. Which version needed the
   fewest new lines?

<details><summary>Answers</summary>

1. It gets slower. Timing `zip` over three columns against `itertuples` over six, both at 100,000 rows, gave about
   0.033 s against 0.060 s. The cost per row has a part that depends on the row's width: Python has to build a bigger
   tuple (and objects for the values you never use). Fetch only the columns you need. The same advice applies to
   `SELECT *` into a DataFrame, and it is why the scripts here use `usecols` when they read the CSVs.
2. SQL: one more expression, `SUM(fan_status = 1 AND duct_static < duct_static_sp - :tol) * :step_h AS fault_h`.
   pandas: one more line, `fault_rows * STEP_H`. The loop needs no new counter here (`fault_rows` already exists),
   but any number that isn't a function of the existing counters needs a new counter *and* a new `if`, and every
   extra number makes the loop longer.

</details>

## Why it matters

Open-FDD ships every rule twice (pandas oracle, SQL pack) because they are better at different jobs, not because one
is always right. Today's tables are the first honest picture of that. Days 17–20 add the other axes: memory (Day 17),
gaps in the data (Day 18), joining another time series (Day 19), and the full scaling showdown (Day 20).
