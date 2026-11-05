# Day 9 — CASE and conditional aggregation: run hours, percent occupied

**Goal:** compute several different counts in one pass using `CASE` inside aggregates.

## Read

`CASE` is SQL's if/else, and it returns a value:

```
CASE WHEN condition THEN a
     WHEN other     THEN b
     ELSE c END
```

Put it inside an aggregate and you get **conditional aggregation**: one scan, many answers.

```
sum(CASE WHEN fan = 1 AND occ = 0 THEN 1 ELSE 0 END)   -- readings: running while unoccupied
avg(CASE WHEN fan = 1 THEN static END)                 -- average static only while running (ELSE → NULL, ignored)
```

In SQLite a comparison is already 0 or 1, so `sum(fan = 1 AND occ = 0)` works too. `CASE` is clearer and portable to
other databases.

The `occupied` role is the AHU's occupancy command: 1 when the schedule says the building is in use. An AHU running
while **unoccupied** is one of the most common energy findings in retro-commissioning (RCx).

## Run

```sql
-- Hours each AHU ran while unoccupied, and was off while occupied
SELECT fp.equipment_id,
       round(sum(CASE WHEN f.value = 1 AND o.value = 0 THEN 1 ELSE 0 END) * 5 / 60.0, 1) AS run_unocc_h,
       round(sum(CASE WHEN f.value = 0 AND o.value = 1 THEN 1 ELSE 0 END) * 5 / 60.0, 1) AS off_occ_h,
       round(100.0 * avg(o.value), 1)                                                   AS pct_occupied
FROM lab_point fp
JOIN samples f    ON f.timeseries_id = fp.timeseries_id
JOIN lab_point op ON op.equipment_id = fp.equipment_id AND op.openfdd_role = 'occupied'
JOIN samples o    ON o.timeseries_id = op.timeseries_id AND o.ts = f.ts
WHERE fp.openfdd_role = 'fan-status'
GROUP BY fp.equipment_id
ORDER BY fp.equipment_id;
-- expect: AHU_1 | 58.6 | 2.2 | 51.3
```

AHU_1 ran about 59 hours while the schedule said unoccupied. AHU_2 has the opposite pattern: 30.8 hours **off**
while occupied, which is a comfort problem rather than an energy one.

```sql
-- Bucket outside air into bands and count
SELECT CASE
         WHEN value < 40 THEN '1: below 40 F'
         WHEN value < 60 THEN '2: 40-60 F'
         WHEN value < 80 THEN '3: 60-80 F'
         ELSE '4: 80 F and up'
       END AS band,
       count(*) AS readings
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
GROUP BY band
ORDER BY band;
-- expect rows: 4
```

## Try it

Solve the week 1 challenge, now with `lab_point` and `CASE`: for each month, AHU_1's average outside air temperature,
fan run hours, and readings with duct static above 1.5.

<details><summary>Answer</summary>

```sql
SELECT strftime('%Y-%m', s.ts, 'unixepoch') AS month,
       round(avg(CASE WHEN p.openfdd_role = 'outside-air-temp' THEN s.value END), 1)            AS avg_oat,
       round(sum(CASE WHEN p.openfdd_role = 'fan-status' THEN s.value ELSE 0 END) * 5 / 60.0, 1) AS run_h,
       sum(CASE WHEN p.openfdd_role = 'duct-static-pressure' AND s.value > 1.5 THEN 1 ELSE 0 END) AS high_static
FROM samples s
JOIN lab_point p ON p.timeseries_id = s.timeseries_id
WHERE p.equipment_id = 'AHU_1'
  AND p.openfdd_role IN ('outside-air-temp', 'fan-status', 'duct-static-pressure')
GROUP BY month
ORDER BY month;
-- expect: 2026-03 | 41.5
```

One scan, three answers. The `CASE` picks which rows feed each column. In week 1 this took three queries, or a
self-join.

</details>

## Why it matters

A fault rule is a `CASE`: *when* the fan runs at full speed *and* static is below setpoint *then* 1 *else* 0. Sum
it and you have fault hours. Day 14 builds exactly that.
