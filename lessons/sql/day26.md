# Day 26 — Read an execution plan and justify an index

[Previous: Day 25](day25.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 27](day27.md)

**Week 4 · 45–75 minutes.** Prerequisites: days 1–25, or equivalent skills.

## Goal

Read the basic shape of an `EXPLAIN` plan and evaluate one scratch index against a concrete access pattern. Preserve query correctness while investigating performance.

## Before you start

Use the disposable course database. `EXPLAIN` describes a planned execution; `EXPLAIN (ANALYZE, BUFFERS)` executes the statement and reports actual work. Today's analyzed statements are bounded `SELECT`s. Applying that option to a write would execute the write.

## Concept

A sequential scan reads table rows and checks conditions. An index scan uses a separate access structure to find candidate rows, then may visit table pages. The planner estimates cost and row counts using statistics. Estimates are not milliseconds, and an index is not automatically faster for a small table or a query reading most rows.

A multicolumn B-tree index has an ordered key. Equality on site and point followed by a timestamp range matches the common point-history access pattern. The existing sample key already supports that pattern; avoid adding a duplicate index simply because a tutorial mentions indexing. Every extra index consumes storage and adds write work.

## Tiny example

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT site_id, point_id, ts, value, quality
FROM course.sample
WHERE site_id = 'SYN-NORTH'
  AND ts >= TIMESTAMPTZ '2026-01-05 08:00:00+00'
  AND ts <  TIMESTAMPTZ '2026-01-05 09:00:00+00'
ORDER BY point_id, ts;
```

The actual result contains 334 rows: two AHUs × fourteen roles × twelve instants, minus two absent pressure rows. Scan and sort choices depend on the server and statistics. Record the plan you observe instead of requiring a particular node name.

## SQL challenge

Create one bounded scratch copy of the fixture with `CREATE TABLE student.day26_sample AS SELECT ... FROM course.sample`. It has 24,190 rows and no copied primary key. Inspect its indexes, run `ANALYZE`, and capture a plan for a single-point half-open time-window lookup using a UUID retrieved from metadata.

Add one scratch index on `(site_id, point_id, ts)`, analyze again, and compare plans for the exact same query. Record result equality, estimated/actual row counts, scan choice, and buffers. A plan that stays sequential can be a valid outcome.

## Experiment

Compare the selective lookup with a query reading most scratch rows. Predict why the useful access strategy might change. Keep both histories bounded to the fixture; do not manufacture millions of rows or run repeated timing loops.

## Acceptance checks

- The example's actual row count reconciles to 334.
- Before/after queries return identical data and your index exists only in `student`.
- You explain one estimated/actual difference or one planner choice without claiming universal speedup.

## Stretch and reflection

Read [week 4 references](SOURCES.md#week-4) for `EXPLAIN`, statistics, and multicolumn indexes. What write cost and storage tradeoff accompanies the index you tested?

[Previous: Day 25](day25.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 27](day27.md)
