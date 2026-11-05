# Day 8 — Self-joins: static pressure *while the fan is running*

**Goal:** line up two different points at the same timestamp, and filter one by the other.

## Read

In long format, the fan status and the duct static pressure at 10:05 are **two different rows** of `samples`. To ask
"what was static pressure while the fan ran?", you need them side by side in one row. That takes a **self-join**:
join `samples` to itself, once for each point, matching on the same `ts`.

```
fan status reading  f   ─┐
                         ├─ same ts, same AHU ─▶ one row: (ts, fan status, static)
static reading      d   ─┘
```

Each copy of `samples` needs its own `lab_point` copy to pick the role:

```
FROM lab_point fp JOIN samples f  ON f.timeseries_id = fp.timeseries_id            -- fan status readings
JOIN lab_point dp ON dp.equipment_id = fp.equipment_id
                 AND dp.openfdd_role = 'duct-static-pressure'                      -- same AHU's static point
JOIN samples d    ON d.timeseries_id = dp.timeseries_id AND d.ts = f.ts            -- its reading at the same time
WHERE fp.openfdd_role = 'fan-status'
```

Matching on `ts` works because this historian logs every point on the same 5-minute grid. If two points were logged
at different times, you'd first round them onto a common grid (Day 10).

## Run

```sql
-- Duct static vs setpoint, only while the supply fan runs
SELECT fp.equipment_id,
       count(*)                     AS running_readings,
       round(avg(d.value), 3)       AS avg_static,
       round(avg(sp.value), 3)      AS avg_setpoint
FROM lab_point fp
JOIN samples f    ON f.timeseries_id = fp.timeseries_id
JOIN lab_point dp ON dp.equipment_id = fp.equipment_id AND dp.openfdd_role = 'duct-static-pressure'
JOIN samples d    ON d.timeseries_id = dp.timeseries_id AND d.ts = f.ts
JOIN lab_point spp ON spp.equipment_id = fp.equipment_id AND spp.openfdd_role = 'duct-static-pressure-sp'
JOIN samples sp   ON sp.timeseries_id = spp.timeseries_id AND sp.ts = f.ts
WHERE fp.openfdd_role = 'fan-status' AND f.value = 1
GROUP BY fp.equipment_id
ORDER BY fp.equipment_id;
-- expect: AHU_1 | 18893 | 1.347 | 1.402
```

Compare with Day 4. Over all hours AHU_1's static averaged 0.78 against a 1.37 setpoint, which looked like a fault.
While running it's 1.35 against 1.40: close, slightly low. AHU_2 runs at **1.40 against a 0.76 setpoint**, well
above. That's worth a look, and it's what a "duct static too high" rule would flag.

## Try it

1. Average discharge air temperature on AHU_1 while the fan runs vs while it's off. Why is the minimum while running
   0.0 °F?
2. Rewrite the first query for the fan **off** (`f.value = 0`). What's static pressure doing then?

<details><summary>Answers</summary>

```sql
SELECT f.value AS fan_status, round(avg(d.value), 1) AS avg_dat, round(min(d.value), 1) AS min_dat
FROM lab_point fp
JOIN samples f    ON f.timeseries_id = fp.timeseries_id
JOIN lab_point dp ON dp.equipment_id = fp.equipment_id AND dp.openfdd_role = 'discharge-air-temp'
JOIN samples d    ON d.timeseries_id = dp.timeseries_id AND d.ts = f.ts
WHERE fp.openfdd_role = 'fan-status' AND fp.equipment_id = 'AHU_1'
GROUP BY f.value ORDER BY f.value;
-- expect: 0 | 70.1 | 45.4
```

Running averages 53.3 °F, off 70.1 °F (the air in the duct drifts toward room temperature). A real discharge
temperature of 0 °F is impossible. It's a dropout: the controller or historian wrote 0 when it had no value. Treat 0
in a temperature column as **missing**, not cold. Fault rules must not fire on it.

```sql
SELECT fp.equipment_id, round(avg(d.value), 3) AS avg_static_fan_off
FROM lab_point fp
JOIN samples f    ON f.timeseries_id = fp.timeseries_id
JOIN lab_point dp ON dp.equipment_id = fp.equipment_id AND dp.openfdd_role = 'duct-static-pressure'
JOIN samples d    ON d.timeseries_id = dp.timeseries_id AND d.ts = f.ts
WHERE fp.openfdd_role = 'fan-status' AND f.value = 0
GROUP BY fp.equipment_id ORDER BY fp.equipment_id;
-- expect rows: 2
```

Near zero, as it should be with the fan off. That's why the Day 4 averages were misleading.

</details>

## Why it matters

Every fault rule is a condition on several points at the same time, gated by "is the equipment on?". Six joins to
line up three points is clumsy, though. On Day 11 you'll pivot the data once into a wide table and write rules as
simple `WHERE` clauses.
