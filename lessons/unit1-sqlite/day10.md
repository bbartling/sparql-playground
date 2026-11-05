# Day 10 — Time buckets and views: hourly averages (what Timescale's `time_bucket` does)

**Goal:** downsample 5-minute data to hourly, and save queries as views and summary tables.

## Read

**Time bucketing.** Integer division rounds a timestamp down to a bucket:

```
ts / 3600 * 3600     -- start of the hour (3600 s)
ts / 900  * 900      -- start of the 15-minute bucket
ts / 86400 * 86400   -- start of the UTC day
```

`ts` is an integer, so `/` drops the remainder. Group by the bucket and aggregate, and you have hourly data.
TimescaleDB, the Postgres extension many historians use, calls this `time_bucket('1 hour', time)`. SQLite does it
with arithmetic.

Always keep a `count(*)` per bucket. A bucket with 4 readings instead of 12 is a partial hour, and its average is less
trustworthy.

**Views.** `CREATE VIEW name AS SELECT ...` saves a query under a name. It stores no data; it reruns every time you
use it. Good for not repeating yourself.

**Summary tables.** `CREATE TABLE name AS SELECT ...` runs the query once and stores the result. It's fast to read,
but stale when new data arrives. Timescale's **continuous aggregates** are this idea maintained for you: a summary
table it refreshes as new data lands. In SQLite you rebuild it yourself.

## Run

```sql
-- Hourly outside air temperature, AHU_1
SELECT datetime(ts / 3600 * 3600, 'unixepoch') AS hour_utc,
       round(avg(value), 2) AS avg_f,
       count(*) AS n
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
GROUP BY ts / 3600
ORDER BY ts / 3600
LIMIT 2;
-- expect: 2026-03-16 00:00:00 | 69.03 | 4
```

The first hour has only 4 readings (00:40–00:55).

```sql
-- A view: every reading with its point attributes
DROP VIEW IF EXISTS lab_reading;
CREATE VIEW lab_reading AS
SELECT p.equipment_id, p.openfdd_role, p.point_id, p.unit, s.ts, s.value
FROM samples s
JOIN lab_point p ON p.timeseries_id = s.timeseries_id;

SELECT count(*) FROM lab_reading WHERE openfdd_role = 'fan-status';
-- expect: 71072
```

```sql
-- A summary table: hourly mean / min / max for every role point
DROP TABLE IF EXISTS lab_hourly;
CREATE TABLE lab_hourly AS
SELECT equipment_id, openfdd_role,
       ts / 3600 * 3600 AS hour_ts,
       avg(value) AS mean, min(value) AS lo, max(value) AS hi, count(*) AS n
FROM lab_reading
WHERE openfdd_role IS NOT NULL
GROUP BY equipment_id, openfdd_role, ts / 3600;

SELECT count(*) FROM lab_hourly;
-- expect: 77012
```

26 role points × 2,962 hours = 77,012 rows, instead of 924k readings. Charts and dashboards read tables like this.

## Try it

1. From `lab_hourly`, the hour with AHU_2's highest average duct static pressure.
2. Write a 15-minute bucket version of the first query. How many readings does a full 15-minute bucket have?

<details><summary>Answers</summary>

```sql
SELECT datetime(hour_ts, 'unixepoch'), round(mean, 3)
FROM lab_hourly
WHERE equipment_id = 'AHU_2' AND openfdd_role = 'duct-static-pressure'
ORDER BY mean DESC
LIMIT 1;
-- expect rows: 1
```

```sql
SELECT datetime(ts / 900 * 900, 'unixepoch') AS bucket, count(*) AS n
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
GROUP BY ts / 900 ORDER BY ts / 900 LIMIT 3;
-- expect: 2026-03-16 00:30:00 | 1
```

A full 15-minute bucket has 3 readings. The first has only one, at 00:40.

</details>

## Week 2 challenge

Build `lab_daily`: one row per AHU per day, with fan run hours, hours run while unoccupied, average outside air
temperature, and average static pressure *while running*. Then find the five days with the most unoccupied runtime on
AHU_1, and check the day of week (`strftime('%w', ...)`): weekends?
