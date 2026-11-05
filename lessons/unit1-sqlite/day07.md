# Day 7 — JOIN: readings by role and equipment instead of UUID

**Goal:** combine `samples` and `lab_point` so you can ask for readings by meaning.

## Read

A **JOIN** pairs rows from two tables that match a condition:

```
FROM samples AS s
JOIN lab_point AS p ON p.timeseries_id = s.timeseries_id
```

For every reading `s`, find the point row `p` with the same `timeseries_id`, and glue them into one wider row.
`s` and `p` are **aliases** (short names), so you can write `s.value` and `p.unit`.

- `JOIN` (inner join) keeps only rows that matched.
- `LEFT JOIN` keeps every row from the left table and fills the right side with NULLs when nothing matched. It's the
  tool for "which readings have no point?" style checks.

Once joined, you filter and group by point attributes: `WHERE p.openfdd_role = 'fan-status'`,
`GROUP BY p.equipment_id`. No UUIDs typed.

## Run

```sql
-- Supply fan run hours for every AHU, no UUIDs typed
SELECT p.equipment_id, round(sum(s.value) * 5 / 60.0, 1) AS run_hours
FROM samples AS s
JOIN lab_point AS p ON p.timeseries_id = s.timeseries_id
WHERE p.openfdd_role = 'fan-status'
GROUP BY p.equipment_id
ORDER BY p.equipment_id;
-- expect: AHU_1 | 1574.4
```

```sql
-- Average discharge vs return air temperature per AHU
SELECT p.equipment_id, p.openfdd_role, round(avg(s.value), 2) AS avg_f
FROM samples AS s
JOIN lab_point AS p ON p.timeseries_id = s.timeseries_id
WHERE p.openfdd_role IN ('discharge-air-temp', 'return-air-temp')
GROUP BY p.equipment_id, p.openfdd_role
ORDER BY p.equipment_id, p.openfdd_role;
-- expect: AHU_1 | discharge-air-temp | 61.17
```

```sql
-- Integrity check: any readings whose UUID is not in the point list?
SELECT count(*)
FROM samples AS s
LEFT JOIN lab_point AS p ON p.timeseries_id = s.timeseries_id
WHERE p.timeseries_id IS NULL;
-- expect: 0
```

Zero orphans. The repo's tests enforce the same invariant on the RDF model: every series in the store has a point,
and every point's series is in the store.

## Try it

1. Average duct static pressure **setpoint** per AHU. Are the two AHUs controlled to the same setpoint?
2. Count readings per `unit`. Which unit has the most data?

<details><summary>Answers</summary>

```sql
SELECT p.equipment_id, round(avg(s.value), 3) FROM samples s
JOIN lab_point p ON p.timeseries_id = s.timeseries_id
WHERE p.openfdd_role = 'duct-static-pressure-sp'
GROUP BY p.equipment_id ORDER BY p.equipment_id;
-- expect: AHU_1 | 1.366
```

AHU_1 averages 1.37 inH2O, AHU_2 0.78. Different setpoints, which is normal: each fan system is sized for its own
ductwork.

```sql
SELECT coalesce(p.unit, '(none)') AS unit, count(*) AS readings
FROM samples s JOIN lab_point p ON p.timeseries_id = s.timeseries_id
GROUP BY unit ORDER BY readings DESC;
-- expect: DEG_F | 2380912
```

`coalesce(x, y)` returns the first non-NULL argument. Here it labels the points that have no unit (statuses,
commands, alarms).

</details>

## Why it matters

"Join readings to metadata, filter by metadata" is exactly what the API does. The difference is that its metadata
comes from a SPARQL query over the graph rather than a table. Week 12's client runs a SPARQL query, gets UUIDs back,
and reads samples. Same join, across two systems.
