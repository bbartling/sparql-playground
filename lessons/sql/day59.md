# Day 59 — Write a parameterized history and plot contract

[Previous: Day 58](day58.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 60](day60.md)

**Week 9 · 45–75 minutes.** Prerequisites: Days 1–58, or equivalent SQL skills.

## Goal

Specify a safe SQL boundary and a small plot-ready response whose scope and units remain visible.

## Before you start

Use the model-to-point resolution learned in week 8. Review the [fixture contract](CONTRACT.md). Write SQL and example JSON as local artifacts; this lesson does not add an endpoint to brickts.

## Concept

A query contract states accepted types, bounds, ordering, authorization scope and failure behavior. Parameter binding supplies values, including UUIDs and timestamps. Identifiers such as table names and sort directions require a fixed allowlist; quoting an arbitrary input does not grant authorization. A SQL `PREPARE` demonstrates binding without choosing a web framework. A plot client needs timestamps, values, units, quality or gaps, and provenance. It does not need the whole joined metadata table for every sample.

## Tiny example

```sql
PREPARE day59(text, uuid, timestamptz, timestamptz, integer) AS
SELECT ts, value, quality
FROM course.sample
WHERE site_id = $1 AND point_id = $2
  AND ts >= $3 AND ts < $4
ORDER BY ts LIMIT $5;
```

Validate `$3 < $4`, allowed window, authorized point ownership and a positive capped `$5` before execution. A limit does not replace these checks. Client-driver placeholders can differ from PostgreSQL prepared-statement syntax.

## SQL challenge

Define a one-point six-hour history contract and a fifteen-minute aggregate contract. Include good sample count and expected count in each aggregate bucket so missing data cannot masquerade as zero. Resolve north Supply A kW for January 5, 15:00–16:00 UTC: raw history has twelve rows, eleven eligible values, and a visible gap at 15:10. Make a minimal JSON example with units, half-open range, identity, model revision, query version and row count.

## Experiment

List outcomes for an invalid UUID, reversed interval, excessive limit, unknown point, wrong site, and an input containing a quote. Distinguish validation errors from valid empty history. Execute the prepared SQL with valid fixture parameters.

## Acceptance checks

- Query text contains no interpolated user values.
- The response represents null/quality without inventing measured zero.
- Scope applies to metadata resolution and sample retrieval.
- Plot arrays cannot silently mismatch timestamps and values.

## Stretch and reflection

Which provenance fields belong once per response, and which belong on individual buckets?

Save your SQL, actual output, and one explanation in `student-work/sql/day59/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-9).

[Previous: Day 58](day58.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 60](day60.md)
