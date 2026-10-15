# Day 68 — Budget database memory and avoid full-history fetches

[Previous: Day 67](day67.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 69](day69.md)

**Week 10 · 45–75 minutes.** Prerequisites: Days 1–67, or equivalent SQL skills.

## Goal

Connect SQL plan operations, concurrency and payload size to a bounded memory budget.

## Before you start

Use at most two lab sessions and the existing two-day data. Keep changes transaction-local. Never change `postgresql.conf`, container memory or shared-server settings for this exercise.

## Concept

`work_mem` is a budget for individual sort/hash operations, with additional details such as `hash_mem_multiplier` and parallel workers. It is not one memory allowance per database. Several operations and sessions can multiply demand. Four sessions with two four-MiB sorts suggest up to 32 MiB for those sort budgets alone; that is not a complete process-memory estimate. PostgreSQL’s [resource settings documentation](https://www.postgresql.org/docs/16/runtime-config-resource.html) describes these limits. Client arrays and JSON encoding consume separate memory.

## Tiny example

```sql
SELECT name, setting, unit
FROM pg_catalog.pg_settings
WHERE name IN ('work_mem', 'hash_mem_multiplier',
               'max_parallel_workers_per_gather')
ORDER BY name;

BEGIN;
SET LOCAL work_mem = '1MB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT point_id, count(*)
FROM student.ts_sample
WHERE site_id = 'SYN-NORTH'
  AND ts >= '2026-01-05 00:00Z'::timestamptz
  AND ts < '2026-01-06 00:00Z'::timestamptz
GROUP BY point_id;
ROLLBACK;
```

No spill is required on this small dataset. Report what the plan shows.

## SQL challenge

Compare a server-side hourly kW aggregation with fetching one equipment’s raw kW day and aggregating in an optional client. Return equal means and coverage. Measure rows transferred and encoded bytes; measure client memory only if you have a suitable tool. Write a budget for two concurrent requests that includes pool capacity, possible sort/hash operations and maximum response rows. Keep caching bounded by entries and bytes.

## Experiment

Describe a cache key containing authorized site, point selection, range, resolution, query version and model/data revision. Change one key component and show why reusing the old answer would be invalid. A missing revision policy is a limitation, not proof of freshness.

## Acceptance checks

- No unbounded `SELECT *` is used as an analytics pipeline.
- Memory claims distinguish measured values from budget estimates.
- Aggregate eligibility and units match both paths.
- Local settings revert after the transaction.

## Stretch and reflection

Which query operations could multiply memory beyond your first estimate?

Save your SQL, actual output, and one explanation in `student-work/sql/day68/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-10).

[Previous: Day 67](day67.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 69](day69.md)
