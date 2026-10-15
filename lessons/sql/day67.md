# Day 67 — Review retention and columnstore as data lifecycle changes

[Previous: Day 66](day66.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 68](day68.md)

**Week 10 · 45–75 minutes.** Prerequisites: Days 1–66, or equivalent SQL skills.

## Goal

Measure a small columnstore conversion and demonstrate retention with an absolute, reviewable cutoff.

## Before you start

Make disposable scratch copies; `course.sample` must remain intact. Keep day66’s aggregate source available. January fixtures are already old relative to today, so do not attach a relative-time retention job to them.

## Concept

Retention drops whole eligible chunks, changing which questions remain answerable. Columnstore changes storage and query tradeoffs while keeping rows queryable. Compare checksums or ordered values before and after conversion. The [2.30.2 policy source](https://raw.githubusercontent.com/timescale/timescaledb/2.30.2/sql/policy_api.sql) defines `add_columnstore_policy` as a procedure; use `CALL`, while `add_retention_policy` is a function. The [matching maintenance source](https://raw.githubusercontent.com/timescale/timescaledb/2.30.2/sql/maintenance_utils.sql) defines `convert_to_columnstore` as a procedure too. Record installed signatures when using another release; old compression examples are not the course API.

## Tiny example

```sql
SELECT n.nspname, p.proname, p.prokind,
       pg_catalog.pg_get_function_arguments(p.oid) AS arguments
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
WHERE p.proname IN ('add_columnstore_policy',
                   'convert_to_columnstore', 'add_retention_policy')
ORDER BY n.nspname, p.proname;
```

`prokind = 'p'` identifies a procedure and `f` a function. This is evidence about the running installation.

## SQL challenge

Create a separate twelve-hour-chunk hypertable copy. Enable columnstore using `timescaledb.enable_columnstore`, segment by site/point and order by time according to the installed release. Convert one explicitly identified scratch chunk with `CALL convert_to_columnstore(...)`. Compare one bounded history query’s rows and plan before and after. Record size information where supported; tiny fixtures need not save space.

## Experiment

On another disposable copy, inspect which chunks precede the absolute cutoff January 6 at 00:00 UTC. Use `drop_chunks` with that timestamp, then verify only January 6 remains: 12,096 rows. Capture eligibility before deleting anything. Explain how a refresh that revisits deleted raw history could change retained aggregates.

## Acceptance checks

- Conversion preserves the selected row set and quality.
- Retention affects only the named scratch table and declared chunks.
- Source fixtures and day66’s restored answer remain unchanged.
- No background lifecycle job is left running.

## Stretch and reflection

Which legal or operational requirement would determine retention in a real deployment? Record it as a requirement to investigate.

Save your SQL, actual output, and one explanation in `student-work/sql/day67/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-10).

[Previous: Day 66](day66.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 68](day68.md)
