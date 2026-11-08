# Day 7 — Two AHUs: stack them, then join them on time

**Goal:** put both AHUs in one table, then JOIN them on `timestamp_utc` to ask "how far apart are two sensors that
measure the same weather?", in SQL and in pandas, and learn how a join actually runs and how it goes wrong.

## Read

Building 50 has two air handlers, AHU_1 and AHU_2, each logged in its own CSV (and its own SQLite table) with the
same column names. Two different questions need two different tools.

**Stack: "give me all the rows."** One table with an `equipment_id` column, so one query covers every AHU. This is
`UNION ALL` in SQL and `pd.concat` in pandas (add the id column to each piece first). Use `UNION ALL`, not `UNION`:
plain `UNION` also removes duplicate rows, which costs a sort and would silently drop legitimate repeats.

**Join: "put the two rows for the same time side by side."** One row per timestamp, one column per AHU. Both AHUs
sit in the same building and see the same weather, so their outside-air temperatures should nearly agree. A big gap
means one sensor is wrong, a better data-quality check than any threshold on a single sensor. The difference of two
converted temperatures is already a *difference* (Day 6): `oa_ahu_1_c - oa_ahu_2_c` is in K, no 32.

Building 50's answer: on average the sensors differ by 1.6 K, 9,005 of 35,536 rows by more than 2 K, and 7 rows by
more than 20 K. Those 7 are AHU_2 reading exactly 0 °F, a sensor dropout: the history's minimum for AHU_2 is
−17.8 °C, about 10 K colder than AHU_1's.

**How a join runs.** Three ways to match the rows:

| Algorithm | How | Cost (n rows probing m rows) | Where you meet it |
|---|---|---|---|
| nested loop | for each left row, scan the whole right table | O(n · m) | a naive double loop |
| nested loop + index seek | for each left row, look the key up in a B-tree | O(n log m) | SQLite, using the primary key |
| hash join | build a hash table of the right side once, probe it per left row | O(n + m) | pandas `merge` |

`timestamp_utc` is the table's primary key, so SQLite already has a B-tree on it, and the plan says
`SEARCH b USING COVERING INDEX sqlite_autoindex_ahu_2_1 (timestamp_utc=?)`. Without an index SQLite doesn't fall back
to the O(n·m) loop: it builds a temporary **automatic index** just for the query. pandas builds a hash table. The
scripts print a timing at the end to show the difference.

**Join explosion.** The one-to-one join above works because `timestamp_utc` is unique in each table. If the join key
repeats, every left row pairs with *every* matching right row. Try joining the first day of the two AHUs on the
**hour** (about 12 rows per hour) instead of the timestamp: 280 rows per side become 3,328 rows. Add up a `SUM` or
`COUNT` over a join like that and every number is silently inflated. pandas has a guard: `merge(...,
validate="1:1")` raises `MergeError` if either side's key repeats (`"1:m"` and `"m:1"` check one side). SQL has no
such keyword; the equivalent is to check `count(*) > count(DISTINCT key)` before you trust a join.

| Step | `day07_sql.py` | `day07_pandas.py` |
|---|---|---|
| stack | `SELECT 'AHU_1' AS equipment_id, ... UNION ALL SELECT 'AHU_2', ...` | `pd.concat(frames)` after `df.insert(0, "equipment_id", ...)` |
| join on time | `FROM ahu_1 a JOIN ahu_2 b ON b.timestamp_utc = a.timestamp_utc` | `a.merge(b, on="timestamp_utc", validate="1:1")` |
| gap stats | `avg(abs(diff_k))`, `sum(abs(diff_k) > 2)` | `diff.abs().mean()`, `(diff.abs() > 2).sum()` |
| key repeats? | `count(*) > count(DISTINCT hour)` | `merge(..., validate="1:1")` raises |

## Run

```bash
uv run python lessons/course.py run 7
```

That runs [`day07_pandas.py`](day07_pandas.py), then [`day07_sql.py`](day07_sql.py). Both print:

```
Outside-air temperature, AHU_1 minus AHU_2 (K):
 paired_rows  mean_abs_diff_k  max_abs_diff_k  rows_over_2k  rows_over_20k
       35536             1.64           39.83          9005              7

Join explosion on one day of data:
 rows_per_side  joined_on_timestamp  joined_on_hour  validate_blocked
           280                  280            3328              True
```

(SQLite prints `1` instead of `True`; the test treats them as equal.) After that, the pandas script times a nested
loop against `merge` (1,500 rows per side: tens of milliseconds against about 1 ms) and the SQL script prints the two
query plans and times them. Your times will differ; the shape won't.

## Try it

1. Change the 2 K threshold to 1 K in both scripts. How many rows are more than 1 K apart?
2. Make it a left join (`LEFT JOIN` / `how="left"`) after deleting one AHU_2 row (in pandas:
   `b = b.drop(b.index[100])`).
   What is `oa_ahu_2_c` on the missing timestamp, and how does that differ from the inner join's result?

<details><summary>Answers</summary>

1. Compare `abs(diff_k) > 1`: 17,215 rows, just under half. The two sensors disagree by more than 1 K for much of
   the record, so a rule that mixes them shouldn't assume they match.
2. The left join keeps the AHU_1 row and fills the AHU_2 value with `NaN` (SQL: `NULL`); the inner join silently
   drops the row, so you would never know a timestamp was missing. Left joins are how you *find* gaps.

</details>

## Why it matters

Stacking and joining are the two shapes of nearly every analysis: "same question for every AHU" and "relate two
measurements at the same time". Both are exact and cheap *when the key is unique and you know it is*. The join
explosion is the classic way an energy or fault number comes out 12× too big and nobody notices. Day 8 adds `CASE`,
so one pass over the rows can answer several conditional questions at once.
