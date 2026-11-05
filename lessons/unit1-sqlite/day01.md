# Day 1 — Open the database; what one row is

**Goal:** open the API's database in DB Browser for SQLite and say in one sentence what a row means.

## Read

An HVAC controller measures things (temperatures, pressures, fan status) and a **historian** saves a reading every
few minutes. Building 50's historian exported a CSV with one column per point. `uv run bldgts bootstrap` turned
that into the API's SQLite database, `var/timeseries.sqlite`.

SQLite is a whole SQL database in one file: no server, no login. Python ships with it (`import sqlite3`), and so
do phones and browsers.

Open it **read-only** this week, so nothing you click can change it:

1. Start DB Browser for SQLite.
2. Click the small arrow next to **Open Database** and choose **Open Database Read Only**.
3. Pick `var/timeseries.sqlite` in this repo.

On the **Database Structure** tab you'll see two tables:

| Table | What it holds |
|---|---|
| `samples` | every reading: `timeseries_id`, `ts`, `value` |
| `ingest_log` | one row per CSV the bootstrap loaded (file hash and row count), so it can skip unchanged files |

Click the arrow next to `samples` to see its columns and the `CREATE TABLE` statement:

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
- `WITHOUT ROWID` stores rows sorted by that key, so all the readings of one point sit together, in time order.
  Day 12 shows why that makes reads fast.

This shape is called **long** (or narrow) format: three columns, millions of rows. The CSV it came from was
**wide**: one row per timestamp and one column per point. Day 11 converts between the two.

Now open **Browse Data**, pick `samples`, and scroll. Then go to **Execute SQL**, paste a query, and press
**Ctrl+Return** (or F5) to run it.

## Run

```sql
-- How many readings are there?
SELECT count(*) FROM samples;
-- expect: 4193248
```

```sql
-- The first five rows, in key order
SELECT * FROM samples LIMIT 5;
-- expect rows: 5
```

```sql
-- What did the bootstrap load?
SELECT dataset_key, row_count FROM ingest_log;
-- expect rows: 2
```

The two `row_count`s (2,949,488 for AHU_1 and 1,243,760 for AHU_2) add up to the total above.

## Try it

1. In **Browse Data**, filter `timeseries_id` by typing the first few characters of any id. Do all its rows share
   the same id and step forward in `ts`?
2. How many different points are there?

<details><summary>Answer</summary>

```sql
SELECT count(DISTINCT timeseries_id) FROM samples;
-- expect: 118
```

118 points (series). 4,193,248 / 118 = 35,536 readings each: every point was logged at every timestamp.

</details>

## Why it matters

Every time-series database (Timescale, InfluxDB, a data lake) stores some version of *(series id, time, value)*.
The hard part is never storing it. It's knowing **which** series id is the duct static pressure on AHU_1. That
knowledge isn't in this table at all, and finding it is what the RDF half of the course is about.
