# Day 2 — SELECT, WHERE, ORDER BY, LIMIT on one sensor; what the UUIDs are

**Goal:** pull the readings of one sensor, sorted and trimmed, and know where its id comes from.

## Read

A `timeseries_id` looks like `bf422925-1e2d-598d-9069-3b0f17d49c48`. That's a **UUID**, a 128-bit id written as 32
hex digits. These are version-5 UUIDs: a hash of a name, so the same building/point always gets the same UUID. They
don't change between rebuilds, and the API can hand them out without exposing the BAS's internal point names.

The database doesn't know what a UUID means. That lives in the point list the model is built from,
`model/points/BUILDING_50__AHU_1.csv`. Open it in a text editor or spreadsheet and find this row:

| source_column | point_id | brick_class | unit | openfdd_role | timeseries_id |
|---|---|---|---|---|---|
| outside_air_temp_f | AHU_1_OA_T | Outside_Air_Temperature_Sensor | DEG_F | outside-air-temp | bf422925-1e2d-598d-9069-3b0f17d49c48 |

So `bf422925…` is AHU_1's outside air temperature in °F. Here are a few you'll use this week:

| Point | timeseries_id |
|---|---|
| AHU_1 outside air temp (°F) | `bf422925-1e2d-598d-9069-3b0f17d49c48` |
| AHU_1 supply fan status (1 = running) | `9ebf80dd-7821-510b-b2c0-cd0151e093c9` |
| AHU_1 duct static pressure (inH2O) | `52422584-9894-50bd-9696-2fbb8b062518` |
| AHU_1 duct static pressure setpoint (inH2O) | `761c2b61-4982-5157-bc66-2010cf6e2a47` |

The parts of a query, in the order you write them:

```
SELECT  columns            -- what to show
FROM    table              -- where from
WHERE   condition          -- which rows
ORDER BY column [DESC]     -- sorted how
LIMIT   n                  -- how many
```

Text values go in single quotes. Double quotes are for column and table names.

## Run

```sql
-- The first three outside air readings
SELECT ts, value
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
ORDER BY ts
LIMIT 3;
-- expect: 1773621600 | 69.0327
```

```sql
-- The hottest reading
SELECT ts, value
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
ORDER BY value DESC
LIMIT 1;
-- expect: 1784065200 | 98.8608
```

```sql
-- Readings above 1.5 inH2O on AHU_1's duct static pressure
SELECT count(*)
FROM samples
WHERE timeseries_id = '52422584-9894-50bd-9696-2fbb8b062518'
  AND value > 1.5;
-- expect: 8336
```

`ts` is a big number. Tomorrow turns it into a date.

## Try it

1. What was the coldest outside air reading?
2. Is AHU_1's supply fan status ever anything other than 0 or 1?

<details><summary>Answers</summary>

```sql
SELECT ts, value FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
ORDER BY value ASC LIMIT 1;
-- expect: 1773740400 | 17.8308
```

```sql
SELECT DISTINCT value FROM samples
WHERE timeseries_id = '9ebf80dd-7821-510b-b2c0-cd0151e093c9'
ORDER BY value;
-- expect rows: 2
```

Only 0 and 1. Status points are numbers in a historian, not booleans.

</details>

## Why it matters

Pasting UUIDs by hand doesn't scale. AHU_1 alone has 83 points, and a campus has tens of thousands. Day 6 puts
the point list in a table, and Unit 4 replaces it with a SPARQL query: "give me the duct static pressure sensor of
every AHU" → UUIDs.
