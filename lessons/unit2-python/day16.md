# Day 16 — One answer three ways: a Python loop, pandas and SQL

**Goal:** compute the same fault count and run hours with a row-by-row Python loop, with vectorized pandas and with
one SQL aggregate; prove they agree; then measure how each one grows with the data, and what moving the data costs.

## Read

Week 4 asks one question over and over: *the answer is the same, so which tool should compute it?* You have written
Open-FDD-style rules in SQL (Unit 1) and in pandas (Day 14). Plain Python is the third option, and the one a CS
course starts with.

Today's job is deliberately small, so the three versions fit on a screen. Take the FC1 raw condition from Day 14
(**fan running and duct static more than 25 Pa below setpoint**) and compute two numbers:

- `fault_rows`: how many 5-minute rows meet the condition;
- `run_hours`: fan run hours, which is rows with `fan_status = 1` times 5 minutes.

How each one does it:

| | Plain Python | pandas | SQL (SQLite) |
|---|---|---|---|
| Where the rows live | `sqlite3` cursor or a list | DataFrame columns (NumPy arrays) | table in the database file |
| Who runs the loop | the interpreter, once per row | compiled C inside NumPy | compiled C inside SQLite |
| Condition | `if fan == 1 and static < sp - tol` | `(fan == 1) & (static < sp - tol)` | `CASE WHEN ... THEN 1 ELSE 0 END` |
| Add them up | `count += 1` | `mask.sum()` | `SUM(...)` |

**Big-O.** All three are O(n): they touch every row once, so ten times the rows costs about ten times the time. Big-O
hides the **constant factor**, and the constant is what you actually wait for. A Python loop pays interpreter
overhead on every row: fetch a tuple, unpack it, run a few bytecodes, update a counter. NumPy and SQLite run the same
logic in compiled loops, so their per-row cost is smaller by one to two orders of magnitude. Same curve, very
different slope.

**The hidden cost: moving data.** The pandas and SQL numbers above assume the data is already where that tool wants
it: in a DataFrame, or in a table. If your data lives in SQLite and you want pandas, you first pay to copy it into
a DataFrame (`read_sql_query`). If it lives in a DataFrame and you want SQL, you pay to insert it (`to_sql`). Those
copies are O(n) too, and they are usually *bigger* than the computation they enable. We time them separately.

## Run

```python
import sqlite3

import numpy as np
import pandas as pd

import lab

conn = (
    lab.connect()
)  # the real Building 50 database; today's benchmarks use throwaway in-memory databases

TOL_PA = 25.0  # tolerance below setpoint, pascals
STEP_H = 5 / 60  # one row = 5 minutes, in hours


def make(n):
    """n rows of synthetic SI history for one AHU, in an in-memory SQLite table `h` and a DataFrame."""
    df = lab.synthetic_history(n)
    mem = sqlite3.connect(":memory:")
    lab.to_sqlite(df, mem, "h", index=["equipment_id", "ts"])
    return df, mem


df, mem = make(5_000)
print(df.head(3).to_string(index=False))
```

**Version (a): a Python loop.** Iterating the cursor streams rows out of SQLite one tuple at a time. Nothing but the
SQL text and three counters is held in Python.

```python
ROWS_SQL = "SELECT fan_status, duct_static, duct_static_sp FROM h"


def loop_answer(conn):
    fault_rows = 0
    run_rows = 0
    for fan, static, sp in conn.execute(ROWS_SQL):
        if fan == 1:
            run_rows += 1
            if static < sp - TOL_PA:
                fault_rows += 1
    return {"fault_rows": fault_rows, "run_hours": run_rows * STEP_H}
```

**Version (b): vectorized pandas.** No loop in your code. Each line is one operation over a whole column.

```python
def pandas_answer(df):
    running = df["fan_status"] == 1
    fault = running & (df["duct_static"] < df["duct_static_sp"] - TOL_PA)
    return {"fault_rows": int(fault.sum()), "run_hours": float(running.sum()) * STEP_H}
```

**Version (c): one SQL aggregate.** The loop moves inside the database. Only one row comes back.

```python
AGG_SQL = """
SELECT SUM(CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END) AS fault_rows,
       SUM(fan_status = 1) * :step_h AS run_hours
FROM h
"""


def sql_answer(conn):
    return lab.query(conn, AGG_SQL, {"tol": TOL_PA, "step_h": STEP_H})
```

Parity first, as always. Three implementations, one answer:

```python
a, b, c = loop_answer(mem), pandas_answer(df), sql_answer(mem)
print("loop  :", a)
print("pandas:", b)
print("sql   :", c.iloc[0].to_dict())
lab.assert_parity(pd.DataFrame([a]), c, label="loop == SQL")
lab.assert_parity(pd.DataFrame([b]), c, label="pandas == SQL")
assert a["fault_rows"] > 0 and a["fault_rows"] == b["fault_rows"] == c.iloc[0].fault_rows
```

`SUM(fan_status = 1)` works because SQLite comparisons evaluate to 0 or 1. And note the cheat in the parity check: the
loop and pandas dicts become one-row DataFrames so the same `lab.assert_parity` can compare them with the SQL result.

**Timing, growing the data.** `lab.best_time` runs a function a few times and keeps the fastest, which hides noise from
whatever else your computer is doing. We build the data once per size (outside the timers), then time only the
computation. Under `course.py check` the sizes shrink automatically.

```python
SIZES = lab.sizes([1_000, 10_000, 100_000, 1_000_000])
rows = []
for n in SIZES:
    df_n, mem_n = make(n)
    reps = 3 if n <= 100_000 else 2
    answers = (loop_answer(mem_n), pandas_answer(df_n), sql_answer(mem_n).iloc[0].to_dict())
    assert (
        answers[0]["fault_rows"] == answers[1]["fault_rows"] == answers[2]["fault_rows"]
    )  # parity at every size
    rows.append(
        {
            "rows": n,
            "loop_s": lab.best_time(lambda: loop_answer(mem_n), reps),
            "pandas_s": lab.best_time(lambda: pandas_answer(df_n), reps),
            "sql_s": lab.best_time(lambda: sql_answer(mem_n), reps),
        }
    )
    mem_n.close()
res = pd.DataFrame(rows)
res["loop/pandas"] = res.loop_s / res.pandas_s
res["loop/sql"] = res.loop_s / res.sql_s
print(res.to_string(index=False, float_format=lambda x: f"{x:,.4g}"))
```

Read the table in two directions. Down a column, the time grows about 10x per row of the table once the data is big
enough to matter: that's O(n). (The smallest sizes are dominated by fixed overhead: starting a query, allocating
arrays.) Across a row, the three tools differ by a constant factor that stays roughly the same at every size. The loop
is the slowest everywhere, and its disadvantage doesn't shrink as the data grows. On the machine this was written on,
SQL was about 6x faster than the loop and pandas over 100x faster. Both are compiled loops, but pandas only has to
compare and add whole arrays in memory, while SQLite evaluates a `CASE` expression per row, decoding each row from its
B-tree pages as it goes.

Sanity-check the growth rather than eyeballing it. Per-row cost should be roughly flat for each tool:

```python
per_row = res.assign(
    loop_us=res.loop_s / res.rows * 1e6,
    pandas_us=res.pandas_s / res.rows * 1e6,
    sql_us=res.sql_s / res.rows * 1e6,
)[["rows", "loop_us", "pandas_us", "sql_us"]]
print(per_row.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
big = res.iloc[-1]
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert big.loop_s > big.pandas_s and big.loop_s > big.sql_s  # the interpreter loop is slowest
```

**What did it cost to get the data there?** Now the part that surprises people. Time the two copies:

```python
move = []
for n in SIZES:
    df_n, mem_n = make(n)
    reps = 3 if n <= 100_000 else 1
    t_read = lab.best_time(
        lambda: pd.read_sql_query("SELECT * FROM h", mem_n), reps
    )  # SQLite -> DataFrame

    def insert():
        scratch = sqlite3.connect(":memory:")
        lab.to_sqlite(df_n, scratch, "h")  # DataFrame -> SQLite
        scratch.close()

    t_insert = lab.best_time(insert, reps)
    t_calc = lab.best_time(lambda: pandas_answer(df_n), reps)
    t_sql = lab.best_time(lambda: sql_answer(mem_n), reps)
    move.append(
        {
            "rows": n,
            "read_sql_s": t_read,
            "to_sql_s": t_insert,
            "pandas_calc_s": t_calc,
            "sql_agg_s": t_sql,
        }
    )
    mem_n.close()
mv = pd.DataFrame(move)
mv["read/calc"] = mv.read_sql_s / mv.pandas_calc_s
mv["load+calc/sql"] = (mv.read_sql_s + mv.pandas_calc_s) / mv.sql_agg_s
print(mv.to_string(index=False, float_format=lambda x: f"{x:,.4g}"))
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert (
        mv.read_sql_s > mv.pandas_calc_s
    ).all()  # copying costs more than the arithmetic it feeds
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert (
        mv["load+calc/sql"].iloc[-1] > 1
    )  # from a table, "load then pandas" loses to one SQL aggregate
```

Loading a table into pandas costs about two orders of magnitude more than the pandas computation itself, and
inserting a DataFrame into SQLite costs about as much (it builds a B-tree and an index entry per row). The last column
is the one to remember: if the data lives in SQLite and you need *one number*, "load into pandas, then compute"
loses to the SQL aggregate, because the aggregate runs where the data is and only one row crosses the boundary.
"pandas is faster than SQL" is only true *once the data is already a DataFrame*. If you will ask fifty questions of
the same data, pay the load once and use pandas. That trade-off is Day 20's main theme.

The worst version of all is the one that looks innocent: loop in Python, but over a list you built with `fetchall()`.
You pay the transfer *and* the interpreter, and hold every row in memory as well. Day 17 measures that memory.

## Try it

1. The loop above reads three columns. What happens to its time if it reads `SELECT *` (six columns) instead?
   Time it at 100,000 rows (use 20,000 under quick mode) and say why.
2. Add a third number to all three versions: the *fault run hours*, `fault_rows * 5 / 60`. Keep parity. Which
   version needed the fewest new lines?

<details><summary>Answers</summary>

```python
n = 20_000 if lab.QUICK else 100_000
df_n, mem_n = make(n)


def loop_star(conn):
    """Same loop, but SELECT * pulls six columns per row; we unpack by position."""
    count = 0
    for _eq, _ts, fan, static, sp, _oat in conn.execute("SELECT * FROM h"):
        if fan == 1 and static < sp - TOL_PA:
            count += 1
    return count


t3 = lab.best_time(lambda: loop_answer(mem_n))
t6 = lab.best_time(lambda: loop_star(mem_n))
print(f"3 columns {t3:.3f} s, 6 columns {t6:.3f} s")
assert loop_star(mem_n) == loop_answer(mem_n)["fault_rows"]
if not lab.QUICK:  # timings: full sizes only (they vary by machine)
    assert t6 > t3

# 2. fault hours in all three versions: one new expression each
fault_h_loop = loop_answer(mem_n)["fault_rows"] * STEP_H
fault_h_pd = pandas_answer(df_n)["fault_rows"] * STEP_H
fault_h_sql = lab.query(
    mem_n,
    "SELECT SUM(fan_status = 1 AND duct_static < duct_static_sp - :tol) * :step_h AS fault_h FROM h",
    {"tol": TOL_PA, "step_h": STEP_H},
)
lab.assert_parity(pd.DataFrame({"fault_h": [fault_h_loop]}), fault_h_sql, label="fault hours loop")
lab.assert_parity(pd.DataFrame({"fault_h": [fault_h_pd]}), fault_h_sql, label="fault hours pandas")
print("fault hours:", fault_h_sql.iloc[0, 0])
mem_n.close()
```

1. It gets slower, because the cost per row has a part that depends on the row's width: SQLite has to decode and
   Python has to build a bigger tuple (and allocate objects for the strings and numbers you never use). Fetch only
   the columns you need. The same advice applies to `SELECT *` into a DataFrame.
2. The SQL version: it already was one expression, so adding another `SUM` is one line. In pandas it's one line
   too. The loop needs a new counter *and* a new `if`, and every extra number makes it longer.

</details>

## Why it matters

Open-FDD ships every rule twice (pandas oracle, SQL pack) because they are better at different jobs, not because one
is always right. Today's table is the first honest picture of that. Days 17–20 add the other axes: memory (Day 17),
gaps in the data (Day 18), joining another time series (Day 19), and the full scaling showdown (Day 20).
