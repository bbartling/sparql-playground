# Day 2 — SELECT, WHERE, ORDER BY, LIMIT on a few columns

**Goal:** pull a few columns of AHU_1, filtered, sorted and trimmed, in pandas and in SQL, and pass values to SQL
safely.

## Read

The parts of a query, in the order you write them, and the pandas that does each job:

```
SELECT  columns            -- what to show            df[["timestamp_utc", "outside_air_temp_f"]]
FROM    table              -- where from              (the DataFrame you loaded)
WHERE   condition          -- which rows              df[df.da_p_inwc > 1.5]
ORDER BY column [DESC]     -- sorted how              .sort_values("outside_air_temp_f", ascending=False)
LIMIT   n                  -- how many                .head(n)
```

Today's columns, all from AHU_1's table `ahu_1`:

| Column | What it is | Unit |
|---|---|---|
| `outside_air_temp_f` | outside air temperature | °F |
| `da_p_inwc` | duct static pressure (the pressure the supply fan builds in the supply duct) | inches of water |
| `da_p_setpoint_inwc` | the pressure the controller is trying to hold | inches of water |
| `supply_fan_status` | 1 when the supply fan is running, 0 when off | 0/1 |

Text values go in single quotes in SQL. Double quotes are for column and table names. To combine conditions use
`AND` / `OR` in SQL and `&` / `|` in pandas. Each condition needs its own parentheses in pandas, because `&` binds
tighter than `>`.

**Parameters, not f-strings.** In Python you'll be tempted to build SQL with an f-string:
`f"... WHERE timestamp_utc = '{ts}'"`. Don't. If `ts` ever comes from a user, a file or an API request, a value like
`x' OR '1'='1` rewrites your query (**SQL injection**), and even with trusted values you get quoting bugs. Instead
leave a placeholder, `?` or a name like `:limit`, and pass the value separately. The database receives the SQL text
and the value as two different things, so a value can never be mistaken for SQL. It also lets SQLite reuse the
compiled query. Every query in this course passes values as parameters; only column and table names (which cannot be
parameters) are written into the SQL text, and those are typed by you, never taken from input.

**Where the work happens.** `timestamp_utc` is the table's `PRIMARY KEY`, and SQLite keeps an index on it: a sorted
B-tree. So `WHERE timestamp_utc >= :start AND timestamp_utc < :end` is a **seek**: walk the tree from the root to the
first matching key, O(log n), then read the k matching rows in order. pandas has no such luxury on a plain column.
`df["timestamp_utc"] >= start` compares every one of the n rows and builds a True/False array of length n: O(n).
(A DataFrame whose index is sorted can do binary search too, but you pay for the sort, and the rows are already in
memory.) A filter on `da_p_inwc` has no index in either tool, so both scan all n rows. `EXPLAIN QUERY PLAN` shows
which one SQLite chose; the SQL script prints it.

A sort is different again: `ORDER BY ... LIMIT 1` only needs the biggest row, and `sort_values(...).head(1)` sorts all
n rows to get it, O(n log n), where a single pass for the maximum would do. (`nlargest(1)` is the pandas way to ask
for just that.) At 35,000 rows nobody notices. At a hundred million rows it is the whole job.

## Run

```bash
uv run python lessons/course.py run 2
```

That runs [`day02_pandas.py`](day02_pandas.py), then [`day02_sql.py`](day02_sql.py). Each step maps like this:

| Step | `day02_sql.py` | `day02_pandas.py` |
|---|---|---|
| pick columns | `SELECT timestamp_utc, outside_air_temp_f` | `df[["timestamp_utc", "outside_air_temp_f"]]` |
| first three | `ORDER BY timestamp_utc LIMIT 3` | `.sort_values("timestamp_utc").head(3)` |
| hottest | `ORDER BY outside_air_temp_f DESC, timestamp_utc LIMIT 1` | `sort_values([...], ascending=[False, True]).head(1)` |
| filter + count | `WHERE da_p_inwc > :limit` + `count(*)` | `(df["da_p_inwc"] > 1.5).sum()` |
| two conditions | `WHERE a = 1 AND b > :min_oat` | `df[(df.a == 1) & (df.b > 95.0)]` |
| time range | `WHERE timestamp_utc >= :start AND timestamp_utc < :end` | two comparisons joined by `&` |
| distinct values | `SELECT DISTINCT supply_fan_status` | `df["supply_fan_status"].unique()` |

In pandas, `df["da_p_inwc"] > 1.5` makes a column of True/False, one per row, and `.sum()` counts the Trues. SQL's
`WHERE` drops the rows and `count(*)` counts what is left. Same answer; SQL never builds the 35,536-element mask.

Adding `timestamp_utc` as a second sort key makes "hottest" deterministic: several readings can tie, because the
sensor value only changes now and then, and without a tiebreaker SQL and pandas are free to return different ones.

Both scripts print:

```
hottest / coldest reading:
            timestamp_utc  outside_air_temp_f
2026-07-14 21:40:00+00:00               98.86
2026-03-17 09:40:00+00:00               17.83

readings with duct static above 1.5 inH2O: 8336

readings on 2026-07-01 (UTC): 288
rows matching a hostile string: 0
fan status takes the values: [0.0, 1.0]
```

The SQL script also prints SQLite's plan for the date range: `SEARCH ahu_1 USING COVERING INDEX
sqlite_autoindex_ahu_1_1 (timestamp_utc>? AND timestamp_utc<?)`. That `SEARCH ... (timestamp_utc>? AND
timestamp_utc<?)` is the B-tree seek. The index has an odd name because `PRIMARY KEY` on a text column makes SQLite
build an automatic index. 288 is 24 hours × 12 readings an hour: a full day of 5-minute data.

**The range query works on text, by luck.** `timestamp_utc` is text, and every value has the same format
(`2026-07-01 00:00:00+00:00`), so comparing the strings alphabetically is the same as comparing the times. That is
the whole reason the bounds in the scripts are written out in full. Day 3 looks at what goes wrong with a shorter
bound like `'2026-07-01'`, and at the proper date functions.

The hostile string `x' OR '1'='1` is passed as the `:ts` parameter. It is treated as a plain timestamp that matches no
row, so the count is 0. Pasted into the SQL with an f-string, it would have turned the `WHERE` into "always true" and
counted all 35,536 rows.

## Try it

1. What was the coldest outside air reading, and when?
2. How many readings have the fan running (`supply_fan_status = 1`) but duct static below 0.5 inH2O? (Both scripts
   pass the limit as a variable or parameter.)
3. Print the five most recent timestamps, newest first.

<details><summary>Answers</summary>

1. 17.83 °F at `2026-03-17 09:40:00+00:00`. It is already in the printout (`ORDER BY outside_air_temp_f,
   timestamp_utc LIMIT 1`).
2. 782 readings, about 65 fan-running hours at pressure well below any normal setpoint (a hint of Day 14's FC1 rule).

   ```python
   n = int(((df["supply_fan_status"] == 1) & (df["da_p_inwc"] < 0.5)).sum())
   ```

   ```python
   conn.execute(
       "SELECT count(*) FROM ahu_1 WHERE supply_fan_status = 1 AND da_p_inwc < :limit", {"limit": 0.5}
   ).fetchone()
   ```

3. Flip the sort: `ORDER BY timestamp_utc DESC LIMIT 5` in SQL,
   `df["timestamp_utc"].sort_values(ascending=False).head(5)` in pandas (or just `df["timestamp_utc"].tail(5)`) in pandas. The newest row is `2026-07-17 09:55:00+00:00`. SQL's
   `DESC` on the primary key reads the B-tree backwards: no sort at all.

</details>

## Why it matters

Almost every analysis step is "some columns, some rows, in some order, not too many". Getting comfortable with that
shape in both tools means you can read other people's queries and DataFrame code as the same thing. Passing values as
parameters is a habit worth forming now: in Week 5 the column and series you ask for will come from a model lookup, not
from your own keyboard, and a value that came from somewhere else must never be able to become part of the query.
