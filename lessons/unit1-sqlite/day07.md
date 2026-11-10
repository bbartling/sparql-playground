# Day 7 — Two AHUs: stack them, then join them on time

**Goal:** put both AHUs in one table (stack), then join them on `timestamp_utc` to ask "how far apart are two sensors
that measure the same weather?", in pandas and SQL.

## Read

Building 50 has two air handlers, AHU_1 and AHU_2, each logged in its own CSV (and its own SQLite table) with the
same column names. Two different questions need two different tools.

**Stack: "give me all the rows."** One table, AHU_2's rows below AHU_1's, with an `equipment_id` column saying who
is who. This is `UNION ALL` in SQL and `pd.concat` in pandas (add the id column to each piece first). Use
`UNION ALL`, not `UNION`: plain `UNION` also removes duplicate rows, which costs a sort and would silently drop
legitimate repeats. The stacked table has 71,072 rows, twice 35,536.

**Join: "put the two rows for the same time side by side."** One row per timestamp, one column per AHU. Both AHUs
sit in the same building and see the same weather, so their outside-air temperatures should nearly agree. A big gap
means one sensor is wrong, a better data-quality check than any threshold on a single sensor. The difference of two
temperatures is a *difference* (Day 6), so it converts with `* 5 / 9`, no 32.

Building 50's answer: on average the sensors differ by 1.64 K, 9,005 of 35,536 rows by more than 2 K, and 7 rows by
more than 20 K. Those 7 are AHU_2 reading exactly 0 °F, a sensor dropout.

| Step | `day07_sql.py` | `day07_pandas.py` |
|---|---|---|
| stack | `SELECT ... FROM ahu_1 UNION ALL SELECT ... FROM ahu_2` | `pd.concat([ahu_1, ahu_2])` |
| join on time | `FROM ahu_1 AS a JOIN ahu_2 AS b ON b.timestamp_utc = a.timestamp_utc` | `ahu_1.merge(ahu_2, on="timestamp_utc")` |
| count rows over a gap | `SUM(diff_k > 2)` | `(diff_k > 2).sum()` |

**How a join runs (for the curious).** For each AHU_1 row the database finds the AHU_2 row with the same timestamp.
`timestamp_utc` is the primary key of each SQLite table, so SQLite looks rows up in an index (cost about n log m).
pandas builds a hash table of one side and probes it (cost about n + m). Both are fast; a naive double loop that
compares every pair (n × m) is not, which you can see by timing 1,500 × 1,500 timestamps in plain Python.

**Join explosion.** The join above works because `timestamp_utc` is unique in each table. If the join key repeats,
every left row pairs with *every* matching right row. Join the first day of the two AHUs on the **hour** (12 rows
per hour) instead of the timestamp and 280 rows per side become 3,328 rows. Add up a `SUM` or `COUNT` over a join like
that and every number is silently inflated. pandas has a guard: `merge(..., validate="1:1")` raises `MergeError` if
either side's key repeats. SQL has no such keyword; check `COUNT(*) > COUNT(DISTINCT key)` before you trust a join.

## Run

```bash
uv run python lessons/course.py run 7
```

That runs [`day07_pandas.py`](day07_pandas.py), then [`day07_sql.py`](day07_sql.py). Both print:

```
Rows in the stacked table: 71072
Rows in the joined table:  35536
Average gap between the sensors (K): 1.64
Rows more than 2 K apart:  9005
Rows more than 20 K apart: 7
```

## Try it

1. Change the 2 K threshold to 1 K in both scripts. How many rows are more than 1 K apart?
2. Make it a left join (`LEFT JOIN` / `how="left"`) after deleting one AHU_2 row (in pandas:
   `ahu_2 = ahu_2.drop(ahu_2.index[100])`). What is the AHU_2 value on the missing timestamp, and how does that
   differ from the inner join's result?
3. Join explosion: in pandas, add `ahu_1["hour"] = ahu_1["timestamp_utc"].str[:13]` (and the same for `ahu_2`),
   then `ahu_1.merge(ahu_2, on="hour")`. How many rows come back? Now add `validate="1:1"` and see the error.

<details><summary>Answers</summary>

1. Compare `diff_k > 1`: 17,215 rows, just under half. The two sensors disagree by more than 1 K for much of the
   record, so a rule that mixes them shouldn't assume they match.
2. The left join keeps the AHU_1 row and fills the AHU_2 value with `NaN` (SQL: `NULL`); the inner join silently
   drops the row, so you would never know a timestamp was missing. Left joins are how you *find* gaps.
3. 35,536 rows per AHU become about 12 times that: each hour repeats 12 times per AHU, so each row matches 12 rows
   on the other side. With `validate="1:1"` pandas raises `MergeError`.

</details>

## Why it matters

Stacking and joining are the two shapes of nearly every analysis: "same question for every AHU" and "relate two
measurements at the same time". Both are exact and cheap *when the key is unique and you know it is*. The join
explosion is the classic way an energy or fault number comes out 12× too big and nobody notices. Day 8 adds `CASE`,
so one pass over the rows can answer several conditional questions at once.
