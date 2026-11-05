# Day 5 — GROUP BY and HAVING: per day, per month, per series

**Goal:** one summary row per group, and keep only the groups you care about.

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

`WHERE` throws away rows before they're grouped. `HAVING` throws away whole groups after. You can't put `avg(...)`
in a `WHERE`, because no group exists yet at that point.

You can group by an expression, such as the date, so `GROUP BY date(ts, 'unixepoch')` gives one row per day. SQLite
lets you use a column alias (`AS day`) in `GROUP BY` and `ORDER BY`.

## Run

```sql
-- Monthly average outside air temperature
SELECT strftime('%Y-%m', ts, 'unixepoch') AS month,
       round(avg(value), 1) AS avg_f
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
GROUP BY month
ORDER BY month;
-- expect: 2026-03 | 41.5
```

```sql
-- The hottest day on average
SELECT date(ts, 'unixepoch') AS day, round(avg(value), 1) AS avg_f
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
GROUP BY day
ORDER BY avg_f DESC
LIMIT 1;
-- expect: 2026-07-02 | 88.3
```

```sql
-- Days that don't have a full 288 readings
SELECT date(ts, 'unixepoch') AS day, count(*) AS n
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
GROUP BY day
HAVING count(*) < 288
ORDER BY day;
-- expect rows: 2
```

The two short days are the first (2026-03-16, starts at 00:40) and the last (2026-07-17, ends at 09:55). There are
no gaps in between. Real historians usually aren't this tidy, so checking is always worth it.

## Try it

1. Readings per series: does every one of the 118 series have the same count?
2. Daily run hours of AHU_1's supply fan. Which day ran longest?

<details><summary>Answers</summary>

```sql
SELECT n AS readings, count(*) AS series
FROM (SELECT timeseries_id, count(*) AS n FROM samples GROUP BY timeseries_id)
GROUP BY n;
-- expect: 35536 | 118
```

One row back means one count for everyone: all 118 series have 35,536 readings. (A query in a `FROM` like this is a
**subquery**: a table made on the fly.)

```sql
SELECT date(ts, 'unixepoch') AS day, round(sum(value) * 5 / 60.0, 1) AS run_hours
FROM samples
WHERE timeseries_id = '9ebf80dd-7821-510b-b2c0-cd0151e093c9'
GROUP BY day
ORDER BY run_hours DESC, day
LIMIT 3;
-- expect rows: 3
```

Several days ran all 24 hours. Is that normal for an office AHU? That's a question for the building's
operators, and it's the kind of finding retro-commissioning starts from.

</details>

## Week 1 challenge

Using only the four UUIDs from Day 2, write **one query** that reports, for each month: the average outside air
temperature, AHU_1's fan run hours, and the number of readings where duct static was above 1.5 inH2O. (Hint: you
can't do it cleanly yet. Try, notice what makes it awkward, and keep the attempt for Day 9.)
