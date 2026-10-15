# Day 65 — Measure chunk pruning and time buckets

[Previous: Day 64](day64.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 66](day66.md)

**Week 10 · 45–75 minutes.** Prerequisites: Days 1–64, or equivalent SQL skills.

## Goal

Use explicit time bounds to reduce chunk work and compare Timescale buckets with PostgreSQL’s fixed-duration bins.

## Before you start

Use `student.ts_sample` from day64. Keep the source fixture unchanged. Record `TimeZone`; use UTC literals and an explicit origin for comparisons. Inspect plans with a local statement deadline.

## Concept

A bucket is a grouping key, not a missing-data repair. `time_bucket` offers Timescale functionality, while PostgreSQL `date_bin` already supports fixed positive intervals. Neither invents an observation for an empty interval. Match origins before comparing results. A filter on the raw timestamp makes the intended range clear and can allow chunk exclusion. Wrapping the timestamp in a date expression can change optimization and timezone meaning; judge the actual plan.

## Tiny example

```sql
SELECT
  date_bin(INTERVAL '15 minutes', ts,
           '2026-01-05 00:00Z'::timestamptz) AS pg_bin,
  time_bucket(INTERVAL '15 minutes', ts,
              '2026-01-05 00:00Z'::timestamptz) AS ts_bin,
  count(*) AS source_rows
FROM student.ts_sample
WHERE site_id = 'SYN-NORTH'
  AND ts >= '2026-01-05 08:00Z'::timestamptz
  AND ts < '2026-01-05 09:00Z'::timestamptz
GROUP BY pg_bin, ts_bin ORDER BY pg_bin;
```

Four equal bucket pairs appear. Their combined source count is 334: two AHUs times fourteen roles times twelve instants, minus two absent samples. Mixed roles are counted here, never averaged together.

## SQL challenge

For north Supply A duct static only, return four fifteen-minute buckets for that hour with average Pa, eligible count and expected count three. The counts should be 3, 2, 2, 3. Compare both bucket functions. Capture bounded plans for this one-hour interval and for both days; annotate chunks scanned or excluded using the nodes your installed version actually reports.

## Experiment

Compare raw timestamp predicates with a `ts::date` predicate for January 5. Preserve identical intended UTC semantics, then explain any plan difference. Do not force a plan merely to obtain a desired screenshot.

## Acceptance checks

- Only one resolved role/unit is averaged.
- Bucket origins and half-open bounds agree.
- Coverage exposes the missing samples without interpolation.
- Plan evidence identifies the time restriction and chunk work.

## Stretch and reflection

Why can calendar-month or daylight-saving buckets require a different comparison from a fixed fifteen-minute interval?

Save your SQL, actual output, and one explanation in `student-work/sql/day65/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-10).

[Previous: Day 64](day64.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 66](day66.md)
