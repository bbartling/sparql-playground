# Day 11 — Long to wide: the `history` table every Open-FDD rule reads

**Goal:** pivot the readings into one row per AHU per timestamp, one column per role.

## Read

Day 8 needed six joins to put three points side by side. Fault rules want *many* points side by side, so do the
pivot once:

```
long (samples + lab_point)                       wide (lab_history)
equipment ts     role          value             equipment ts     fan_status duct_static duct_static_sp ...
AHU_1     10:05  fan-status    1          ──▶     AHU_1     10:05  1          1.31        1.40
AHU_1     10:05  duct-static   1.31
AHU_1     10:05  duct-static-sp 1.40
```

The SQL trick is **conditional aggregation** again (Day 9): group by `(equipment_id, ts)`, and for each column pick
the value of one role.

```
MAX(CASE WHEN openfdd_role = 'duct-static-pressure' THEN value END) AS duct_static
```

Each group has exactly one reading per role, so `MAX` simply picks it. The other rows give NULL, which `MAX` ignores.

Open-FDD's SQL rules (see `open-fdd/sql_rules/*.sql`) all read a relation called `history` with columns named after
roles: `fan_status`, `fan_cmd`, `duct_static`, `duct_static_sp`, `sat`, `mat`, `rat`, `oat`… The column names below
follow that **input contract**, so a rule written against it doesn't care which building it runs on.

You'll make it a **table**, not a view: the pivot reads 924k rows and takes a few seconds. As a table it's built once
and every rule after that is fast (the Day 10 summary-table idea).

## Run

```sql
DROP TABLE IF EXISTS lab_history;
CREATE TABLE lab_history AS
SELECT p.equipment_id, s.ts,
  MAX(CASE WHEN p.openfdd_role = 'fan-status'              THEN s.value END) AS fan_status,
  MAX(CASE WHEN p.openfdd_role = 'fan-cmd'                 THEN s.value END) AS fan_cmd,
  MAX(CASE WHEN p.openfdd_role = 'duct-static-pressure'    THEN s.value END) AS duct_static,
  MAX(CASE WHEN p.openfdd_role = 'duct-static-pressure-sp' THEN s.value END) AS duct_static_sp,
  MAX(CASE WHEN p.openfdd_role = 'discharge-air-temp'      THEN s.value END) AS sat,
  MAX(CASE WHEN p.openfdd_role = 'discharge-air-temp-sp'   THEN s.value END) AS sat_sp,
  MAX(CASE WHEN p.openfdd_role = 'mixed-air-temp'          THEN s.value END) AS mat,
  MAX(CASE WHEN p.openfdd_role = 'return-air-temp'         THEN s.value END) AS rat,
  MAX(CASE WHEN p.openfdd_role = 'outside-air-temp'        THEN s.value END) AS oat,
  MAX(CASE WHEN p.openfdd_role = 'outside-air-damper'      THEN s.value END) AS oa_damper,
  MAX(CASE WHEN p.openfdd_role = 'cooling-valve'           THEN s.value END) AS clg_valve,
  MAX(CASE WHEN p.openfdd_role = 'occupied'                THEN s.value END) AS occupied
FROM samples s
JOIN lab_point p ON p.timeseries_id = s.timeseries_id
WHERE p.openfdd_role IS NOT NULL
GROUP BY p.equipment_id, s.ts;

SELECT count(*) FROM lab_history;
-- expect: 71072
```

2 AHUs × 35,536 timestamps. Browse it in DB Browser: it looks like the original CSV again, but with standard column
names.

```sql
-- Day 8's six-join query, now one line of logic
SELECT equipment_id, round(avg(duct_static), 3), round(avg(duct_static_sp), 3), count(*)
FROM lab_history
WHERE fan_status = 1
GROUP BY equipment_id
ORDER BY equipment_id;
-- expect: AHU_1 | 1.347 | 1.402 | 18893
```

## Try it

1. Data quality: how many rows have the fan running but a discharge, mixed or return air temperature of exactly 0?
2. What's missing from this pivot if a role has **no** point on some AHU? (Think about what the column would hold.)

<details><summary>Answers</summary>

```sql
SELECT count(*) FROM lab_history
WHERE fan_status = 1 AND (sat = 0 OR mat = 0 OR rat = 0);
-- expect: 14
```

Fourteen dropout rows while running: rare, but each one could trip a rule ("discharge air 50 °F below setpoint!").
Production rules filter or flag them.

2. The column would be NULL for that AHU. That's correct: "not measured" is not 0. A rule that needs that role must
   then **skip** the AHU and say so, rather than invent data. Open-FDD's contract calls that "skipped / not
   applicable".

</details>

## Why it matters

Which UUID becomes `duct_static` for which AHU is a **metadata** question. Here `lab_point.openfdd_role` answered
it. In Unit 4 a SPARQL query will: "for each AHU, the point with role duct-static-pressure and its
`ref:hasTimeseriesId`". That's the model-driven way to build this exact table for any building.
