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
memory.) A filter on `da_p_inwc` has no index in either tool, so both scan all n rows. `EXPLAIN QUERY PLAN` in
front of a query shows which one SQLite chose (Try it 4).

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
| 2. pick columns, first three | `SELECT timestamp_utc, outside_air_temp_f ... ORDER BY timestamp_utc LIMIT 3` | `df[["timestamp_utc", "outside_air_temp_f"]].head(3)` |
| 3. coldest | `ORDER BY outside_air_temp_f, timestamp_utc LIMIT 1` | `sort_values(["outside_air_temp_f", "timestamp_utc"]).head(1)` |
| 4. filter + count | `WHERE da_p_inwc > :limit` + `COUNT(*)` | `df[df["da_p_inwc"] > LIMIT_INWC]`, then `len(...)` |
| 5. two conditions | `WHERE supply_fan_status = 1 AND da_p_inwc < 0.5` | `df[fan_on & static_low]` |

In pandas, `df["da_p_inwc"] > 1.5` makes a column of True/False, one per row, and `df[...]` keeps the True rows. SQL's
`WHERE` drops the rows and `COUNT(*)` counts what is left. Same answer; SQL never builds the 35,536-element mask.

Adding `timestamp_utc` as a second sort key makes "coldest" deterministic: several readings can tie, because the
sensor value only changes now and then, and without a tiebreaker SQL and pandas are free to return different ones.

Both scripts print:

```
            timestamp_utc  outside_air_temp_f
2026-03-16 00:40:00+00:00             69.0327
2026-03-16 00:45:00+00:00             69.0327
2026-03-16 00:50:00+00:00             69.0327
Coldest reading:
            timestamp_utc  outside_air_temp_f
2026-03-17 09:40:00+00:00             17.8308
Readings with static above 1.5 inH2O: 8336
Fan on but static below 0.5 inH2O: 782
```

782 readings with the fan running but almost no duct pressure: about 65 hours, well below any normal setpoint. That is
a first hint of Day 14's FC1 rule.

The SQL script passes the 1.5 limit as the `:limit` parameter, never pasted into the SQL text. The second query
writes its numbers (1 and 0.5) straight into the SQL: that is fine for numbers you typed yourself, and Try it 2 turns
them into parameters.

## Try it

1. What was the **hottest** outside air reading, and when? (Flip step 3's sort.)
2. Step 5's SQL writes `1` and `0.5` into the query text. Turn `0.5` into a parameter, the way step 4 passes
   `:limit`, and check you still get 782.
3. Print the five most recent timestamps, newest first.
4. Put `EXPLAIN QUERY PLAN` in front of two queries: one day of readings by `timestamp_utc`
   (`>= '2026-07-01 00:00:00+00:00' AND < '2026-07-02 00:00:00+00:00'`), and step 4's `da_p_inwc > 1.5`. What does
   SQLite say it does for each?
5. Count the rows `WHERE timestamp_utc = :ts` with `ts = "x' OR '1'='1"` passed as a parameter. Then paste the same
   value into the SQL with an f-string. What changes?

<details><summary>Answers</summary>

1. 98.86 °F at `2026-07-14 21:40:00+00:00`: `ORDER BY outside_air_temp_f DESC, timestamp_utc LIMIT 1` in SQL,
   `sort_values(["outside_air_temp_f", "timestamp_utc"], ascending=[False, True]).head(1)` in pandas.
2. ```python
   sql = "SELECT COUNT(*) FROM ahu_1 WHERE supply_fan_status = 1 AND da_p_inwc < :low"
   fan_on_low = conn.execute(sql, {"low": 0.5}).fetchone()[0]
   ```

   Still 782. In pandas the 0.5 is already an ordinary Python value.
3. Flip the sort: `ORDER BY timestamp_utc DESC LIMIT 5` in SQL, `df.sort_values("timestamp_utc",
   ascending=False).head(5)` in pandas (or just `df.tail(5)`). The newest row is `2026-07-17 09:55:00+00:00`. SQL's
   `DESC` on the primary key reads the B-tree backwards: no sort at all.
4. `SEARCH ahu_1 USING COVERING INDEX sqlite_autoindex_ahu_1_1 (timestamp_utc>? AND timestamp_utc<?)` for the day:
   the B-tree seek. The index has an odd name because `PRIMARY KEY` on a text column makes SQLite build an automatic
   index. For `da_p_inwc > 1.5` it says `SCAN ahu_1`: no index, so every row is read.
5. As a parameter: 0 rows. The value is treated as a plain (odd) timestamp that matches nothing. Pasted in with an
   f-string, the `WHERE` becomes "always true" and you get all 35,536 rows: SQL injection.

</details>

## Why it matters

Almost every analysis step is "some columns, some rows, in some order, not too many". Getting comfortable with that
shape in both tools means you can read other people's queries and DataFrame code as the same thing. Passing values as
parameters is a habit worth forming now: in Week 5 the column and series you ask for will come from a model lookup, not
from your own keyboard, and a value that came from somewhere else must never be able to become part of the query.
