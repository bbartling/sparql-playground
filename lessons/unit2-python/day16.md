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

The data is **synthetic** this week, so we can make it as big as we like. `uv run python lessons/course.py setup`
wrote a million rows of two made-up AHUs (500,000 each, one row every 5 minutes, in SI units) to
`var/synthetic_ahu.csv`, and the same rows to the `synthetic` table in `var/lessons.sqlite`. It has a daily fan
schedule, duct static tracking its setpoint with noise, and a weak-fan window. Columns: `equipment_id`, `ts` (Unix
seconds), `fan_status`, `static_pa`, `setpoint_pa`, `oat_c`. Both scripts take the **first n rows** (n = 10,000,
100,000 and 1,000,000), so they see identical data.

How each one does it:

| | Plain Python (in `day16_pandas.py`) | pandas (`day16_pandas.py`) | SQL (`day16_sql.py`) |
|---|---|---|---|
| Where the rows live | Python lists pulled out of the columns | DataFrame columns (NumPy arrays) | table in the database |
| Who runs the loop | the interpreter, once per row | compiled C inside NumPy | compiled C inside SQLite |
| Condition | `if fan[i] == 1` and `if static[i] < setpoint[i] - TOLERANCE_PA` | `fan_on & too_low` | `fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa` |
| Add them up | `fault_rows = fault_rows + 1` | `.sum()` | `SUM(...)` |

**Big-O.** All three are O(n): they touch every row once, so ten times the rows costs about ten times the time. Big-O
hides the **constant factor**, and the constant is what you actually wait for. A Python loop pays interpreter
overhead on every row: fetch a value, compare, update a counter. NumPy and SQLite run the same logic in compiled
loops, so their per-row cost is smaller by one to two orders of magnitude. Same curve, very different slope.

**The hidden cost: moving data.** The pandas and SQL numbers assume the data is already where that tool wants it:
in a DataFrame, or in a table. If your data lives in SQLite and you want pandas, you first pay to copy it into a
DataFrame (`read_sql_query`). If it lives in a CSV, you pay to parse it (`read_csv`). Those copies are O(n) too, and
they are usually *bigger* than the computation they enable. Each script times the move it can see: the pandas
script, reading the CSV; the SQL script, reading the table out into a DataFrame.

## Run

```bash
uv run python lessons/course.py run 16
```

That runs [`day16_pandas.py`](day16_pandas.py), then [`day16_sql.py`](day16_sql.py) (a few seconds each). The pandas
script has step 2, a plain Python loop, and step 3, the same count with pandas:

```python
for i in range(n):
    if fan[i] == 1:
        run_rows = run_rows + 1
        if static[i] < setpoint[i] - TOLERANCE_PA:
            fault_rows = fault_rows + 1
```

```python
fan_on = df["fan_status"] == 1
too_low = df["static_pa"] < df["setpoint_pa"] - TOLERANCE_PA
pandas_fault_rows = (fan_on & too_low).sum()
```

The SQL script moves the loop inside the database, and one row comes back:

```sql
SELECT SUM(fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa) AS fault_rows,
       SUM(fan_status = 1) * :hours_per_row AS run_hours
FROM synthetic
WHERE rowid <= :n
```

`SUM(fan_status = 1)` works because SQLite comparisons evaluate to 0 or 1. Both scripts print the same counts for
every size (`fault_by_size` in `RESULTS`); the pandas script also checks the loop against pandas. The timings are
**printed, never compared**: they differ on every machine and every run. On the machine this was written on:

```
rows: 10000
  fault rows: 1442
  run hours:  419.3
  loop gives the same answer: True
  seconds: read CSV 0.006 | loop 0.001 | pandas 0.0004
rows: 100000
  fault rows: 14428
  run hours:  4164.0
  loop gives the same answer: True
  seconds: read CSV 0.032 | loop 0.006 | pandas 0.0006
rows: 1000000
  fault rows: 133994
  run hours:  41664.0
  loop gives the same answer: True
  seconds: read CSV 0.291 | loop 0.067 | pandas 0.0057
```

```
rows: 1000000
  fault rows: 133994
  run hours:  41664.0
  seconds: SQL aggregate 0.0946 | read rows into pandas 1.506
```

Read the numbers in two directions. Down the sizes, the time grows about 10x per step once the data is big enough to
matter: that's O(n). (The smallest size is dominated by fixed overhead: starting a query, allocating arrays.) Across
one size, the tools differ by a constant factor. At a million rows the loop took about 0.07 s, the SQL aggregate
about 0.09 s and pandas about 0.006 s, ten times faster than either. Both pandas and SQLite are compiled loops, but
pandas only has to compare and add whole arrays in memory, while SQLite evaluates the expression per row, decoding
each row from its B-tree pages as it goes. (This loop is quick because it reads ready-made Python lists; Try it 1
shows what a loop over DataFrame rows costs.)

**What did it cost to get the data there?** Now the part that surprises people. Reading the CSV took 0.29 s, fifty
times the pandas count. The SQL script's "read rows into pandas" is the move from a table into a DataFrame, with no
computation at all: 1.5 s at a million rows, about 15 times the SQL aggregate that answers the question in place.
Moving data costs one to three orders of magnitude more than the pandas arithmetic: reading a table out builds a
Python tuple per row before converting to arrays, and parsing a CSV turns text back into numbers. If the data lives
in SQLite and you need *one number*, "load into pandas, then compute" loses badly to the SQL aggregate, because the
aggregate runs where the data is and only one row crosses the boundary. "pandas is faster than SQL" is only true
*once the data is already a DataFrame*. If you will ask fifty questions of the same data, pay the load once and use
pandas. That trade-off is Day 20's main theme.

The worst version of all is the one that looks innocent: loop in Python, but over a list you built with `fetchall()`.
You pay the transfer *and* the interpreter, and hold every row in memory as well. Day 17 measures that memory.

## Try it

1. Change the loop to read DataFrame rows instead of lists: `for row in df.itertuples():` with `row.fan_status`,
   `row.static_pa`, `row.setpoint_pa`. Time it at 100,000 rows and say why it changed.
2. Add a third number to all three versions: the *fault hours*, `fault_rows * 5 / 60`. Which version needed the
   fewest new lines?
3. Time the opposite move: writing the DataFrame into a new SQLite table, `df.to_sql("copy", conn)` on an in-memory
   database (`sqlite3.connect(":memory:")`). How does it compare to the pandas count?

<details><summary>Answers</summary>

1. It gets about eight times slower (0.045 s against 0.006 s here). `itertuples` builds a tuple with *every* column of the row (and objects for the
   values you never use) before your `if` runs. Fetch only the columns you need. The same advice applies to
   `SELECT *` into a DataFrame, and it is why the course scripts use `usecols` when they read the CSVs.
2. SQL: one more expression, `SUM(fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa) * :hours_per_row AS
   fault_h`. pandas: one more line, `pandas_fault_rows * HOURS_PER_ROW`. The loop needs no new counter here
   (`fault_rows` already exists), but any number that isn't a function of the existing counters needs a new counter
   *and* a new `if`, and every extra number makes the loop longer.
3. About 1.5 s at a million rows: a few hundred times the pandas count. Inserting builds a B-tree page by page, and Python
   hands each row over one at a time.

</details>

## Why it matters

Open-FDD ships every rule twice (pandas oracle, SQL pack) because they are better at different jobs, not because one
is always right. Today's tables are the first honest picture of that. Days 17–20 add the other axes: memory (Day 17),
gaps in the data (Day 18), joining another time series (Day 19), and the full scaling showdown (Day 20).
