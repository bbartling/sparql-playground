# Day 4 — Summary stats: COUNT, MIN, MAX, AVG, SUM

**Goal:** summarize a sensor in one row, and turn a status point into run hours.

## Read

**Aggregate functions** fold many rows into one value:

| Function | Notes |
|---|---|
| `count(*)` | rows |
| `count(value)` | rows where `value` is not NULL |
| `min(value)`, `max(value)` | ignore NULLs |
| `avg(value)` | mean of the non-NULL values |
| `sum(value)` | total |
| `round(x, n)` | n decimal places, for reading, not storage |

Without `GROUP BY` (tomorrow), an aggregate query returns exactly one row.

A useful trick: a status point is 1 when running and 0 when off. With one reading every 5 minutes,
`sum(status) × 5 / 60` is the **run hours**. Use `60.0`, not `60`: integer division in SQL drops the remainder.

## Run

```sql
-- AHU_1 outside air temperature, whole dataset
SELECT count(*) AS n,
       round(min(value), 2) AS min_f,
       round(max(value), 2) AS max_f,
       round(avg(value), 3) AS avg_f
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48';
-- expect: 35536 | 17.83 | 98.86 | 61.276
```

```sql
-- The same for one day
SELECT round(min(value), 1), round(max(value), 1), round(avg(value), 1)
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
  AND ts >= unixepoch('2026-07-01') AND ts < unixepoch('2026-07-02');
-- expect: 79.9 | 97.1 | 88.3
```

```sql
-- AHU_1 supply fan run hours
SELECT round(sum(value) * 5 / 60.0, 1) AS run_hours
FROM samples
WHERE timeseries_id = '9ebf80dd-7821-510b-b2c0-cd0151e093c9';
-- expect: 1574.4
```

The dataset covers about 2,961 hours, so the fan ran a bit over half the time.

## Try it

1. What are the average duct static pressure and its average setpoint on AHU_1? Which is bigger?
2. What fraction of the time was AHU_1's fan running? (Hint: the average of a 0/1 column is the fraction.)

<details><summary>Answers</summary>

```sql
SELECT round(avg(value), 3) FROM samples
WHERE timeseries_id = '52422584-9894-50bd-9696-2fbb8b062518';
-- expect: 0.783
```

```sql
SELECT round(avg(value), 3) FROM samples
WHERE timeseries_id = '761c2b61-4982-5157-bc66-2010cf6e2a47';
-- expect: 1.366
```

```sql
SELECT round(avg(value), 3) FROM samples
WHERE timeseries_id = '9ebf80dd-7821-510b-b2c0-cd0151e093c9';
-- expect: 0.532
```

The average static (0.78) is far below the average setpoint (1.37). But that includes all the hours the fan was
off, when static is near zero. Day 8 asks the fair question: what is static *while the fan runs*?

</details>

## Why it matters

Averages over everything hide what matters. A sensor reading 0 °F because the unit is off pulls the average down
just like a cold day does. Most of fault detection is asking "the average **of what, when**?" That's filtering
(Days 8–9) and gating (week 3).
