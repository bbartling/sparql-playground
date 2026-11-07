# Day 1 — Open the database; what one row is

**Goal:** open the API's database from Python and say in one sentence what a row means.

## Read

An HVAC controller measures things (temperatures, pressures, fan status) and a **historian** saves a reading every
few minutes. Building 50's historian exported a CSV with one column per point. `uv run bldgts bootstrap` turned
that into the API's SQLite database, `var/timeseries.sqlite`.

SQLite is a whole SQL database in one file: no server, no login. Python ships with it (`import sqlite3`), and so
do phones and browsers.

This course is driven from Python. Each lesson is a Markdown file whose ```python blocks you can paste into a
REPL or notebook, or run top to bottom with `uv run python lessons/course.py run 1`. That command works on a
**temporary copy** of the database, so nothing you try can change `var/timeseries.sqlite`. (DB Browser for SQLite
is still handy as a *viewer*: open the file read-only and browse. It is optional.)

Every computation is done **twice**, the way Open-FDD tests its rules:

- as **SQL**: a SQLite query held in a Python string, run through `lab.query`, which returns a DataFrame;
- as **pandas**: the same answer from a DataFrame, as an independent "oracle";
- then `lab.assert_parity(pandas_result, sql_result)` fails loudly if the two ever differ.

If you know pandas, SQL is the other way to say the same thing. If you know SQL, pandas is. Doing both is how
you learn which one to reach for. A rough map for this week:

| Question | SQL (runs inside the database) | pandas (runs on data already in memory) |
|---|---|---|
| which rows | `WHERE` | boolean mask, `df[mask]` |
| which columns | `SELECT a, b` | `df[["a", "b"]]` |
| sorted | `ORDER BY` | `sort_values` |
| first n | `LIMIT n` | `head(n)` |
| one number from many rows | `count`, `avg`, `sum` ... | `.count()`, `.mean()`, `.sum()` ... |
| one row per group | `GROUP BY` | `groupby(...).agg(...)` |

The big difference is **where the data lives**. A SQL query is sent to the database and only the *answer* comes
back. With pandas you first pull the rows into Python, then work on them. Much of this week is about when that
matters.

## The samples table

The first block opens the database and reads its structure from SQLite's own catalog, `sqlite_master`.

```python
import time

import numpy as np
import pandas as pd

import lab

conn = lab.connect()  # sqlite3.connect() on the course database

tables = lab.query(
    conn,
    "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'lab\\_%' ESCAPE '\\'",
)
print(tables.name.tolist())
print(tables.set_index("name").loc["samples", "sql"])
assert set(tables.name) == {"samples", "ingest_log"}
```

| Table | What it holds |
|---|---|
| `samples` | every reading: `timeseries_id`, `ts`, `value` |
| `ingest_log` | one row per CSV the bootstrap loaded (file hash and row count), so it can skip unchanged files |

The `CREATE TABLE` for `samples`:

```
CREATE TABLE samples (
    timeseries_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    value REAL,
    PRIMARY KEY (timeseries_id, ts)
) WITHOUT ROWID
```

Read it like this:
- **One row is one reading:** this point (`timeseries_id`) had this `value` at this time (`ts`).
- The **primary key** `(timeseries_id, ts)` means a point can't have two readings at the same moment.
- `WITHOUT ROWID` stores the rows *in a B-tree sorted by that key*, so all the readings of one point sit together,
  in time order. Day 2 and Day 12 show why that makes reads fast.

This shape is called **long** (or narrow) format: three columns, millions of rows. The CSV it came from was
**wide**: one row per timestamp and one column per point. Day 11 converts between the two. A pandas DataFrame can
be either; `SELECT * FROM samples` gives you a long one.

## Run

**How many readings are there?** In SQL it's one aggregate. In pandas we have to load the table first.

```python
COUNT_SQL = "SELECT count(*) AS n FROM samples"
t = time.perf_counter()
count_sql = lab.query(conn, COUNT_SQL)
t_count = time.perf_counter() - t
print(count_sql)

t = time.perf_counter()
samples = lab.query(
    conn, "SELECT timeseries_id, ts, value FROM samples"
)  # all rows, loaded ONCE this lesson
t_load = time.perf_counter() - t
count_pd = pd.DataFrame({"n": [len(samples)]})

lab.assert_parity(count_pd, count_sql, label="row count")
assert count_sql.n[0] == 4_193_248
```

Both say 4,193,248. Notice what it cost, though.

```python
print(f"count(*) in SQL:        {t_count * 1000:9.1f} ms   (returns 1 row)")
print(f"load into pandas first: {t_load * 1000:9.1f} ms   (returns {len(samples):,} rows)")
```

`count(*)` on a table stored as a B-tree walks the tree's leaf pages without building a single Python object. It
is still O(n) in the worst case, but it moves **one number** into Python. pandas had to *materialise* 4.2 million
rows first: also O(n), plus a copy of every row across the SQLite/Python boundary and a few hundred MB of
memory. Pushing work into SQL means fewer bytes cross that boundary. This is the only time this lesson loads
the whole table; most of the work this week loads one series (about 35,000 rows).

**The first five rows, in key order.**

```python
FIRST5_SQL = "SELECT timeseries_id, ts, value FROM samples LIMIT 5"
first5_sql = lab.query(conn, FIRST5_SQL)
print(first5_sql)

# `samples` came back in primary-key order, so head() is the same five rows. (SQL promises no order without
# ORDER BY; it is key order here only because that is how the B-tree is laid out. Day 2 sorts explicitly.)
lab.assert_parity(samples.head(5), first5_sql, label="first five rows")
assert len(first5_sql) == 5
```

**What did the bootstrap load?**

```python
LOG_SQL = "SELECT dataset_key, row_count FROM ingest_log ORDER BY dataset_key"
log_sql = lab.query(conn, LOG_SQL)
print(log_sql.to_string(index=False))
assert len(log_sql) == 2
assert log_sql.row_count.tolist() == [2_949_488, 1_243_760]
assert log_sql.row_count.sum() == len(samples)
```

The two `row_count`s (2,949,488 for AHU_1 and 1,243,760 for AHU_2) add up to the total above.

## Try it

1. Pick any `timeseries_id` from `samples` and look at its rows. Do all its rows share the same id and step
   forward in `ts`? (pandas: `samples[samples.timeseries_id == some_id]`; SQL: a `WHERE`, with the id passed as a
   parameter, not pasted into the string. Day 2 explains why.)
2. How many different points are there?

<details><summary>Answer</summary>

```python
some_id = samples.timeseries_id.iloc[0]
one_pd = samples[samples.timeseries_id == some_id].reset_index(
    drop=True
)  # O(n): looks at every row
one_sql = lab.query(
    conn,
    "SELECT timeseries_id, ts, value FROM samples WHERE timeseries_id = ? ORDER BY ts",  # B-tree seek
    (some_id,),
)
lab.assert_parity(one_pd, one_sql, keys=["ts"], label="one series")
assert one_sql.ts.is_monotonic_increasing and one_sql.ts.is_unique
print(one_sql.ts.diff().value_counts())  # every step is 300 s
assert one_sql.ts.diff().dropna().eq(300).all()

DISTINCT_SQL = "SELECT count(DISTINCT timeseries_id) AS series FROM samples"
distinct_sql = lab.query(conn, DISTINCT_SQL)
distinct_pd = pd.DataFrame({"series": [samples.timeseries_id.nunique()]})
lab.assert_parity(distinct_pd, distinct_sql, label="distinct series")
assert distinct_sql.series[0] == 118
assert len(samples) // 118 == 35_536
```

118 points (series). 4,193,248 / 118 = 35,536 readings each: every point was logged at every timestamp.

</details>

## Why it matters

Every time-series database (Timescale, InfluxDB, a data lake) stores some version of *(series id, time, value)*.
The hard part is never storing it. It's knowing **which** series id is the duct static pressure on AHU_1. That
knowledge isn't in this table at all, and finding it is what the RDF half of the course is about.
