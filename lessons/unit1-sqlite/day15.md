# Day 15 — What production does differently (Timescale), and the UUID bridge to RDF

**Goal:** know which parts of Unit 1 carry over to a production historian, and see where the RDF model picks up.

## Read

### SQLite here, Timescale in production

Open-FDD's production stack keeps history in **PostgreSQL + TimescaleDB**. Everything you wrote this unit is plain
SQL and carries over. The differences are operational:

| Need | This course (SQLite) | Timescale |
|---|---|---|
| Store readings | `samples(timeseries_id, ts, value)`, key on series + time | a **hypertable**: same columns, split into time **chunks** automatically, so "last week" only touches a few chunks |
| Bucket by time | `ts / 3600 * 3600` | `time_bucket('1 hour', time)` |
| Summary tables | `CREATE TABLE lab_hourly AS ...`, rebuilt by hand | **continuous aggregates**, refreshed incrementally as data arrives |
| Old data | keep everything | **compression** and **retention policies** per chunk |
| Many writers and readers | one writer at a time | a server with concurrent connections and roles |
| Wide `history` input | `lab_history` table | a view or temporary table built for one site, then the rule SQL runs as is |

The rules don't change. The Open-FDD SQL you read yesterday runs on Postgres with small dialect changes
(`sql/fdd/README.md` lists them). SQLite needs a few more, like sample standard deviation, which it lacks.

### The UUID bridge

All unit long you used `lab_point` to know that `52422584-…` is AHU_1's duct static pressure. The API doesn't use a
table for that. It uses the RDF model, `model/building_50.ttl`. Open it in a text editor and search for
`52422584-9894-50bd-9696-2fbb8b062518`:

```turtle
bldg:AHU_1_DA_P a bts:Entity ;
    rdfs:label "AHU1 DA-P" ;
    ref:hasExternalReference [ a ref:TimeseriesReference ;
            ref:hasTimeseriesId "52422584-9894-50bd-9696-2fbb8b062518" ;
            ref:storedAt bldg:timeseries_db ] ;
    bts:hasHaystackMarker "air", "discharge", "his", ...
```

Read it as statements, each one **subject, predicate, object**:

- `AHU_1_DA_P` has label "AHU1 DA-P".
- `AHU_1_DA_P` has an external reference, a TimeseriesReference with id `52422584-…`, stored at
  `bldg:timeseries_db`.
- `AHU_1_DA_P` has the Haystack markers `air`, `discharge`, …

And further down, `bldg:timeseries_db` describes the database you've been querying, including its schema:
`samples(timeseries_id TEXT, ts INTEGER epoch-s UTC, value REAL)`.

So the model is a graph of statements about things, and one kind of statement points into the time-series store by
UUID. Units 2–4 teach you to store, query and build graphs like this. Then the question "give me duct static and fan
status for every AHU" is answered by the model. The answer comes back as UUIDs, and those go into the SQL you already
know.

## Run

```sql
-- What the course added to the API's database
SELECT type, name FROM sqlite_master WHERE name LIKE 'lab_%' ORDER BY type, name;
```

```sql
-- The one-line summary of Unit 1: confirmed FC1 hours per AHU per month
SELECT equipment_id, strftime('%Y-%m', ts, 'unixepoch') AS month,
       round(sum(fault) * 5 / 60.0, 1) AS fc1_hours
FROM lab_fc1
GROUP BY equipment_id, month
ORDER BY equipment_id, month;
-- expect: AHU_1 | 2026-03
```

When you're done, `uv run python lessons/course.py reset` drops every `lab_*` object. The API's data is untouched.

## Unit 1 challenge

Write a **discharge air temperature** rule for AHU_1 and AHU_2: while the fan runs, discharge air temperature (`sat`)
is more than 5 °F away from its setpoint (`sat_sp`) for at least 30 minutes. Then:

1. Exclude dropout rows (`sat = 0`) and explain how many rows that removed.
2. Report fault hours per AHU per month.
3. Pick the worst day and chart `sat`, `sat_sp` and `fan_status` for it in DB Browser's **Plot** tab.
4. Write two sentences an operator could act on.

Next: **Unit 2** builds a tiny triple store in Python, so the Turtle above stops being mysterious.
