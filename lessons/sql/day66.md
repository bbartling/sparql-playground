# Day 66 — Track continuous aggregate freshness

[Previous: Day 65](day65.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 67](day67.md)

**Week 10 · 45–75 minutes.** Prerequisites: Days 1–65, or equivalent SQL skills.

## Goal

Separate a continuous aggregate’s stored answer from the freshness of its source data.

## Before you start

Use the scratch hypertable from day64. Keep policy scheduling off for these historical January fixtures. Work with explicit refresh intervals and record each source edit and refresh. Run refresh calls in autocommit, outside `BEGIN`/`COMMIT`; commit source corrections first.

## Concept

A continuous aggregate stores summaries maintained by refresh work. Its materialized data can lag behind inserts or corrections. Real-time behavior is a separate setting, and does not automatically repair every historical change. A response therefore needs a source range, refresh information and a freshness policy. [Timescale’s refresh guide](https://www.tigerdata.com/docs/build/continuous-aggregates/refresh-policies) explains the distinction between refresh offsets and their execution schedule. A current-time policy may never revisit this old fixture.

## Tiny example

```sql
CREATE MATERIALIZED VIEW student.hourly_value
WITH (timescaledb.continuous,
      timescaledb.materialized_only = true) AS
SELECT site_id, point_id, time_bucket(INTERVAL '1 hour', ts) AS bucket,
       avg(value) AS mean_value, count(*) AS good_count
FROM student.ts_sample
WHERE quality = 'good' AND value IS NOT NULL
GROUP BY site_id, point_id, bucket
WITH NO DATA;

CALL refresh_continuous_aggregate('student.hourly_value',
  '2026-01-05 00:00Z'::timestamptz,
  '2026-01-07 00:00Z'::timestamptz);
```

Each row has one point’s hourly mean in that point’s unit. Mixed units remain separate by UUID.

## SQL challenge

Compare the materialized and raw hourly answers for north Supply A kW at January 5, 15:00 UTC. Both should have eleven eligible rows averaging 12 kW. Change one eligible scratch source value from 12 to 24, commit, and capture the stale materialized answer. Refresh exactly that hour; the new mean should be `144.0/11`. Restore the source value and refresh again.

## Experiment

Add a historical correction outside a hypothetical policy’s refresh window. Explain why running that policy would not necessarily fix it. Record a proposed bounded backfill procedure; do not create an open-ended refresh job.

## Acceptance checks

- Before, stale and refreshed results are all preserved.
- The eleven-row denominator is explicit.
- Source restoration returns the original answer.
- The design distinguishes source revision, completed refresh and response time.

## Stretch and reflection

When could retaining old aggregates while deleting raw data conflict with a later refresh?

Save your SQL, actual output, and one explanation in `student-work/sql/day66/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-10).

[Previous: Day 65](day65.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 67](day67.md)
