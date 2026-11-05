# Day 6 — A point list table (`lab_point`), and why it's a stand-in for the RDF model

**Goal:** get the point list into the database, so queries can say "duct static pressure" instead of a UUID.

## Read

The UUID → meaning mapping lives in `model/points/*.csv`, one file per AHU. Today you load both files into one
table, `lab_point`. From now on you'll **write** to the database, so:

1. In DB Browser, **Close Database**, then open `var/timeseries.sqlite` normally (not read-only).
2. Close it again before running the command below, because SQLite lets only one writer at a time.
3. In a terminal, in the repo:

   ```bash
   uv run python lessons/course.py load-points
   ```

4. Reopen the database. A new table, `lab_point`, has one row per point:

| Column | Example | Meaning |
|---|---|---|
| `timeseries_id` | `52422584-…` | joins to `samples.timeseries_id` |
| `point_id` | `AHU_1_DA_P` | a readable name for the point |
| `equipment_id` | `AHU_1` | which AHU's mapping file it came from |
| `owner_id` | `AHU_1_Supply_Fan` | the piece of equipment the point belongs to |
| `brick_class` | `Supply_Air_Static_Pressure_Sensor` | what kind of point it is (Brick vocabulary, Unit 3) |
| `unit` | `IN_H2O` | engineering unit |
| `openfdd_role` | `duct-static-pressure` | the role a fault rule asks for, if any |
| `source_column` | `da_p_inwc` | the column name in the BAS export |

(DB Browser can also do this itself: **File → Import → Table from CSV file**. The script just adds `equipment_id`,
which isn't a column in the files.)

**Why this table is a compromise.** Look at `owner_id`: the supply fan status belongs to `AHU_1_Supply_Fan`, which
is part of `AHU_1`. Zone temperatures belong to `Zone_VAV_107`, which AHU_1 feeds. A flat table holds *one*
"belongs to" column. A building is a **graph**: fans are part of AHUs, AHUs feed zones, sensors are points of
equipment. You'll be tempted to write `owner_id LIKE 'AHU_1%'`. That works here by luck of the naming and breaks
on the next site. The RDF model stores those relationships explicitly (`brick:isPartOf`, `brick:feeds`,
`brick:isPointOf`), and Units 3–4 query them with SPARQL. For three weeks of SQL, this table is enough.

## Run

```sql
SELECT count(*), count(openfdd_role), count(DISTINCT brick_class) FROM lab_point;
-- expect: 118 | 26 | 30
```

`count(openfdd_role)` skips NULLs, so 26 of the 118 points have a fault-rule role: 13 per AHU.

```sql
SELECT equipment_id, count(*) AS points
FROM lab_point
GROUP BY equipment_id
ORDER BY equipment_id;
-- expect: AHU_1 | 83
```

```sql
-- The 13 roles on AHU_1
SELECT openfdd_role, point_id, unit, timeseries_id
FROM lab_point
WHERE equipment_id = 'AHU_1' AND openfdd_role IS NOT NULL
ORDER BY openfdd_role;
-- expect rows: 13
```

`IS NOT NULL`, never `!= NULL`: any comparison with NULL is unknown, so `= NULL` and `!= NULL` match nothing.

## Try it

1. What is AHU_2's duct static pressure UUID?
2. Why does AHU_1 have 83 points but AHU_2 only 35? Look at `brick_class`.

<details><summary>Answers</summary>

```sql
SELECT timeseries_id FROM lab_point
WHERE equipment_id = 'AHU_2' AND openfdd_role = 'duct-static-pressure';
-- expect: f8a0d594-2fff-567a-9853-71ba66233eba
```

```sql
SELECT equipment_id, count(*) FROM lab_point
WHERE brick_class = 'Zone_Air_Temperature_Sensor'
GROUP BY equipment_id;
-- expect: AHU_1 | 47
```

AHU_1's export included the zone temperatures of the VAV boxes it serves (47 of them). AHU_2's didn't. Same kind of
building, different export: a point list tells you what was **exported**, not what exists.

</details>

## Why it matters

`lab_point` is a lookup table: id → attributes. In week 5 you'll build the same thing as a dict in Python, then as a
set of triples `(point, hasUnit, IN_H2O)`. That's the shape of RDF.
