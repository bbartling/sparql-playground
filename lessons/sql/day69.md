# Day 69 — Measure bounded scale with declared limits

[Previous: Day 68](day68.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 70](day70.md)

**Week 10 · 45–75 minutes.** Prerequisites: Days 1–68, or equivalent SQL skills.

## Goal

Produce a reproducible scale comparison whose data volume, concurrency and conclusions are explicit.

## Before you start

Set a cap of 241,900 synthetic rows, two clients and twenty measured queries. Use a disposable scratch table, a five-second statement timeout and a total run deadline. Stop on repeated timeout, disk pressure or unexpected row growth.

## Concept

Scale testing asks whether results and resource use remain acceptable as a declared dimension grows. It does not require millions of rows. Moving fixture copies forward in time tests a longer history while keeping point count constant; it does not simulate more buildings or ingestion contention. Report these limitations. Keep query parameters and indexes stable when comparing storage strategies, then explain any intentional difference.

## Tiny example

```sql
SELECT count(*) AS proposed_rows,
       min(s.ts + g.n * INTERVAL '2 days') AS first_ts,
       max(s.ts + g.n * INTERVAL '2 days') AS last_ts
FROM course.sample AS s
CROSS JOIN generate_series(0, 9) AS g(n);
```

This computes the proposed shape without creating a larger table. It yields 241,900 rows and twenty days of shifted fixture data. Timestamps stay distinct within each original point.

## SQL challenge

Choose three sizes up to the cap, such as one, three and ten fixture copies. Build your own scratch dataset and document its key, indexes and partition interval. Compare a fixed one-hour point query and a whole-test-range hourly aggregate. Record actual plans, row counts, database/extension versions, timings and query parameters. Compare raw aggregation with a deliberately refreshed summary where available. Validate answers before comparing speed.

## Experiment

Run the six size/query pairs twice with one client: twelve statements. Choose two pairs for a two-client replay: four more statements. Count failed attempts toward the twenty-statement cap. Report individual timings; summarize distributions only when sample size supports them. Include timeout and failure counts. Do not describe a short local test as a production capacity guarantee.

## Acceptance checks

- Generation stops at or below 241,900 rows, with no duplicate keys.
- Every query has an explicit time interval and result bound.
- Fixed-window answers remain equivalent as unrelated history grows.
- The report states which scale dimensions did and did not change.
- Scratch objects and any jobs have a documented cleanup plan.

## Stretch and reflection

What next experiment would isolate point-count growth from history-length growth?

Save your SQL, actual output, and one explanation in `student-work/sql/day69/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-10).

[Previous: Day 68](day68.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 70](day70.md)
