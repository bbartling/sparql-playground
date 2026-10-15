# Day 64 — Create a time-partitioned scratch hypertable

[Previous: Day 63](day63.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 65](day65.md)

**Week 10 · 45–75 minutes.** Prerequisites: Days 1–63, or equivalent SQL skills.

## Goal

Explain what a Timescale hypertable changes and preserve sample identity when partitioning by time.

## Before you start

Use the Timescale lab described in [Lab guide](LAB_GUIDE.md). Week 10 requires the extension: a plain PostgreSQL session cannot execute these examples. Record `version()` and `pg_extension.extversion`; the validated baseline is PostgreSQL 16.15 with TimescaleDB 2.30.2. If unavailable, record the blocked lab rather than reporting a pass. Never install extensions on a shared server.

## Concept

A hypertable presents one SQL table while storing rows in time chunks. Partitioning supports pruning and chunk lifecycle operations; it does not remove the need for selective predicates or indexes. Every unique constraint must include all partition dimensions. With time as the only dimension, `(site_id, point_id, ts)` remains valid. A unique `(site_id, point_id)` would incorrectly forbid history and cannot enforce uniqueness across time partitions. See [Timescale’s unique-index requirements](https://github.com/timescale/Tiger-Data-Docs/blob/main/src/content/docs/build/performance-optimization/hypertables-and-unique-indexes.mdx).

## Tiny example

```sql
SELECT extversion FROM pg_catalog.pg_extension
WHERE extname = 'timescaledb';

CREATE TABLE student.chunk_demo (
  ts timestamptz NOT NULL, item integer NOT NULL,
  PRIMARY KEY (item, ts)
);
SELECT create_hypertable(
  'student.chunk_demo', by_range('ts', INTERVAL '12 hours'));
```

Use an empty scratch name. This supported conversion API makes the time dimension explicit without creating a wall-clock lifecycle policy.

## SQL challenge

Create `student.ts_sample` with the same six columns, quality/finite checks and logical key as `course.sample`. Convert the empty table to a hypertable with twelve-hour chunks, then copy exactly the fixture rows. Keep metadata in `course`; no extra hash dimension is needed. Inspect `timescaledb_information.hypertables`, `dimensions` and `chunks`. State whether this scratch copy includes foreign keys, and why that matters.

## Experiment

In a separate disposable table, attempt a unique key that omits `ts`; record the rejection and recover cleanly. Inspect the indexes actually created on the valid hypertable instead of assuming a particular name.

## Acceptance checks

- The copy contains 24,190 rows and preserves the one bad/null value.
- Four twelve-hour chunks cover the two-day fixture.
- Repeating a logical key is rejected.
- The extension version and partition/index definitions are saved.

## Stretch and reflection

How would adding a second partition dimension change every unique constraint? What workload would justify it?

Save your SQL, actual output, and one explanation in `student-work/sql/day64/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-10).

[Previous: Day 63](day63.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 65](day65.md)
