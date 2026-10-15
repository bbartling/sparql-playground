# Day 53 — Resolve a point reference before a bounded SQL read

[Previous: Day 52](day52.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 54](day54.md)

**Week 8 · 45–75 minutes.** Prerequisites: Days 1–52, or equivalent SQL skills.

## Goal

Follow the model's timeseries reference into a parameterized, bounded read without deriving keys from labels or IRIs.

## Before you start

Run `uv run python lessons/sql/graph_lab.py lessons/sql/sparql/day53_power_refs.rq`. It returns power-point metadata for three AHUs. The database backend is `postgresql`; the connection property contains the environment-variable name `COURSE_DSN`, never its value.

## Concept

The read path is point → `ref:hasExternalReference` → `ref:TimeseriesReference` → `ref:hasTimeseriesId` plus `ref:storedAt`. The database IRI selects the configured store adapter. The opaque timeseries ID selects history within that store. Validate exactly one reference, one ID and one database before reading.

For this teaching fixture only, the frozen timeseries ID equals SQL `point_id`. An adapter must declare that mapping; another historian may use a different opaque key. The IRI suffix, equipment label and original CSV column are not alternate runtime lookups. Keep site scope as well as point identity when reading `course.sample`.

## Tiny example

```sql
PREPARE day53_read (text, uuid, timestamptz, timestamptz) AS
SELECT ts, value, quality
FROM course.sample
WHERE site_id = $1 AND point_id = $2
  AND ts >= $3 AND ts < $4
ORDER BY ts
LIMIT 12;
```

This prepares a statement with bound values; it does not execute a sample read. Use a discovered site/ID and explicit UTC boundaries when executing or calling a driver. Never concatenate graph text into SQL syntax.

## SQL challenge

Resolve one discovered power point with `graph_lab.py --resolve POINT_IRI`, replacing `POINT_IRI` with its returned full IRI. Record the returned ID and database. Read a bounded hour using parameters, retain quality and compare the result with the same point selected through SQL metadata. Write the adapter contract connecting graph fields to SQL parameters.

## Experiment

Specify a deliberately nonexistent opaque ID in a scratch read. Compare an empty history result with a graph reference that failed cardinality validation. Explain why those require different error messages.

## Acceptance checks

- Discovery returns three power references with `unit:KiloW` and one configured database.
- `--resolve` returns point, timeseries ID and database; it reads no samples.
- A one-hour, complete power window has twelve rows; Jan 5 15:00–16:00Z north Supply A includes one bad/null reading.
- History is bounded and values are bound separately from SQL text.

## Stretch and reflection

Which component would change if history moved to a lakehouse while point identities remained stable? Explain how the metadata and store-adapter boundary supports that change.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day53/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-8) for exact language and domain details.

[Previous: Day 52](day52.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 54](day54.md)
