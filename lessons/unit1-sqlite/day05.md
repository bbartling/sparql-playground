# Day 5 — GROUP BY and HAVING: per day, per month, and the Week 1 challenge

**Goal:** one summary row per group, keep only the groups you care about, in pandas and in SQL, and answer a
three-measure question per month.

## Read

`GROUP BY` splits rows into groups. Each aggregate is then computed once per group:

```
SELECT group_columns, aggregates
FROM ...
WHERE   row filter           -- before grouping
GROUP BY group_columns
HAVING  group filter          -- after grouping, can use aggregates
ORDER BY ...
```

`WHERE` throws away rows before they are grouped. `HAVING` throws away whole groups after. You can't put `avg(...)`
in a `WHERE`, because no group exists yet at that point.

You can group by an expression, such as the date: `GROUP BY date(timestamp_utc)` gives one row per day, and
`strftime('%Y-%m', timestamp_utc)` one row per month (Day 3's date functions). SQLite lets you use a column alias
(`AS day`) in `GROUP BY` and `ORDER BY`. The pandas version of each clause:

| SQL | pandas |
|---|---|
| `WHERE cond` | `df[mask]` before the `groupby` |
| `GROUP BY key` | `df.groupby(key)` (key can be a column or a computed Series, like a formatted date) |
| `avg(c)`, `count(*)`, `sum(c)` | `.agg(avg_f=("c", "mean"), n=("c", "size"), ...)` |
| `HAVING count(*) < 288` | filter **after** the groupby: `grouped[grouped.n < 288]` |
| `ORDER BY x DESC LIMIT 1` | `.sort_values("x", ascending=False).head(1)` |
| `sum(da_p_inwc > 1.5)` | `(df.da_p_inwc > 1.5).sum()` |

So `HAVING` is not a special pandas feature. It is just an ordinary filter on the small table `groupby` gives you.
`WHERE` and `HAVING` differ in SQL only because of clause order; in pandas the order of your statements says it.

**Counting with a comparison.** In SQLite a comparison such as `da_p_inwc > 1.5` is `1` when true and `0` when false,
so `sum(da_p_inwc > 1.5)` counts the rows where it holds, in the same pass as any other aggregate. pandas does the
same with a boolean column (`True` is 1 when you `sum`). That makes "count the readings that meet a condition, per
group" a one-liner, and it is the shape most fault-detection summaries take.

**How each engine groups.** pandas **hashes**: one pass over the rows, each row dropped into a bucket for its key,
O(n). SQLite either **sorts** the rows by the key (into a temporary B-tree) and sums runs of equal keys, O(n log n),
or, if the rows already come out in key order, streams them without a sort. `timestamp_utc` is the primary key, so rows
come out in time order, but a *day* is computed from it and SQLite doesn't know the computed values are in order, so
`GROUP BY date(timestamp_utc)` needs the temporary B-tree. `EXPLAIN QUERY PLAN` in front of the query says so:
`SCAN ahu_1 | USE TEMP B-TREE FOR GROUP BY`. At 35,536 rows this costs nothing you can notice.

## Run
```bash
uv run python lessons/course.py run 5
```

That runs [`day05_pandas.py`](day05_pandas.py), then [`day05_sql.py`](day05_sql.py). Each step maps like this:

| Step | `day05_sql.py` | `day05_pandas.py` |
|---|---|---|
| 2. month and day labels | `strftime('%Y-%m', timestamp_utc)`, `date(timestamp_utc)` | `time.dt.strftime("%Y-%m")`, `"%Y-%m-%d"` |
| 3. one row per month | `GROUP BY month` + `AVG`, `SUM`, `SUM(da_p_inwc > 1.5)` | `df.groupby("month").agg(...)` |
| 4. hottest day | `GROUP BY day ORDER BY avg_f DESC LIMIT 1` | `groupby("day")[...].mean()`, then `idxmax()` |
| 5. short days | `GROUP BY day HAVING COUNT(*) < 288` | `groupby("day").size()`, then a filter on `n < 288` |

Both print:

```
  month  avg_oat_f  fan_run_hours  static_above_1_5
2026-03       41.5          182.7                 0
2026-04       53.0          341.9                 0
2026-05       59.8          331.7                 0
2026-06       71.3          411.6              4721
2026-07       80.0          306.6              3615
Hottest day: 2026-07-01 average (F): 88.3
       day   n
2026-03-16 280
2026-07-17 120
```

1 July (88.30) edges out 2 July (88.25) by 0.04 °F, so the two look tied at one decimal. The sort used the unrounded
averages. Round for display only.

The two short days are the first (2026-03-16, starts at 00:40, 280 readings) and the last (2026-07-17, ends at 09:55,
120 readings). There are no gaps in between. Real historians usually aren't this tidy, so checking is always worth it.
The short days need `HAVING` in SQL because the condition is on a count, which only exists after grouping; in pandas
it is an ordinary filter on the small grouped table.

## Try it

1. AHU_1's fan run hours per month: which month had the most?
2. Which months had any readings with duct static above 1.5 inH2O? (Use the Week 1 challenge's output.)
3. Show only the months where AHU_1's fan ran more than 400 hours. Where does that condition go, `WHERE` or `HAVING`?

<details><summary>Answers</summary>

1. June, with 411.6 hours (March 182.7, April 341.9, May 331.7, July 306.6; March and July are partial months).
2. Only June (4,721 readings on AHU_1) and July (3,615). In March, April and May AHU_1's static never went above 1.5.
   In pandas: filter the monthly table with `monthly[monthly["static_above_1_5"] > 0]`.
3. `HAVING`, because it is a condition on an aggregate (`sum(...)`) of the group:

   ```sql
   SELECT strftime('%Y-%m', timestamp_utc) AS month, sum(supply_fan_status) * 5 / 60.0 AS run_hours
   FROM ahu_1
   GROUP BY month
   HAVING sum(supply_fan_status) * 5 / 60.0 > 400
   ```

   Only `2026-06` comes back. In pandas it is `monthly[monthly["fan_run_hours"] > 400]`, after the groupby.

</details>

## Week 1 challenge

For each month, report **the average outside air temperature, the fan run hours, and the number of readings where
duct static was above 1.5 inH2O**.

This is step 3 in both scripts, the first table they print. Try writing it yourself first, in each tool, before you
read the scripts' versions. What to notice:

- In the old long layout the three measures lived in three different series, and one query could not easily combine
  them. In the wide table all three are columns of the same row, so one `GROUP BY` and three aggregates answer the
  question: `AVG(outside_air_temp_f)`, `SUM(supply_fan_status) * 5 / 60.0`, `SUM(da_p_inwc > 1.5)`.
- Then do it for **both AHUs** in one table: ten rows, two AHUs × five months. `equipment_id` is not a column of
  either table, so add it as you stack them: `SELECT 'AHU_1' AS equipment_id, ... FROM ahu_1 UNION ALL SELECT
  'AHU_2', ... FROM ahu_2` in SQL, `df["equipment_id"] = "AHU_1"` on each DataFrame and `pd.concat` in pandas. Then
  group by two keys, `equipment_id` and `month`.

Static above 1.5 shows up only once it is warm, in June and July, for both AHUs. Next week's questions are about
*why*, and whether that is a problem: AHU_1's average setpoint is 1.37 inH2O, so a reading above 1.5 might be
the system doing exactly what it was asked.

## Why it matters

A summary table per day or per month is the first thing a building owner will ask for, and `GROUP BY` plus a filter on
the groups is how every such table is made. The group key does a lot of quiet work: group by a date you computed in UTC
and "a day" starts at 7 pm local time in summer, which is a mistake you will not see in the numbers. Before judging a
reading you also have to say *which* readings count (when the fan is on, when the building is occupied).
