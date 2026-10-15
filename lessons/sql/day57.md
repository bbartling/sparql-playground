# Day 57 — Read an execution plan before adding an index

[Previous: Day 56](day56.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 58](day58.md)

**Week 9 · 45–75 minutes.** Prerequisites: Days 1–56, or equivalent SQL skills.

## Goal

Explain how a bounded historian query reaches its rows and decide whether an index serves that access pattern.

## Before you start

Run the lab check. Keep the 24,190-row fixture intact. Use scratch copies in `student` for index changes and `ANALYZE`; record server version, query parameters and cache conditions. An observed plan on this fixture is evidence about this fixture.

## Concept

The grain is one site, opaque point UUID and instant. The sample primary key supports equality on site and point followed by a time range. `EXPLAIN` estimates work; `EXPLAIN (ANALYZE, BUFFERS)` executes the statement and reports observed work. Read estimated versus actual rows, loops, filters, sorting and buffers together. A sequential scan can be sensible for a small table or broad range. A `LIMIT` bounds returned rows but does not guarantee a bounded scan or aggregate.

## Tiny example

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT s.ts, s.value
FROM course.sample AS s
WHERE s.site_id = 'SYN-NORTH'
  AND s.point_id = (
    SELECT p.point_id FROM course.point AS p
    JOIN course.equipment AS e USING (site_id, equipment_id)
    WHERE p.site_id = 'SYN-NORTH'
      AND e.label = 'Supply B' AND p.role = 'kw')
  AND s.ts >= '2026-01-05 10:00Z'::timestamptz
  AND s.ts < '2026-01-05 11:00Z'::timestamptz
ORDER BY s.ts LIMIT 12;
```

This demonstration returns twelve six-kW samples. The metadata subquery resolves identity before history selection.

## SQL challenge

Make a scratch sample copy and compare a scoped, one-hour north Supply A kW query with and without an appropriate composite index. Use January 5 at 15:00 UTC: twelve source rows include eleven eligible values. Preserve bad/null rows in raw history, then express eligibility separately. Explain why a value-only index is a poor starting point for this read contract.

## Experiment

Widen the range to both fixture days. Predict how selectivity changes before capturing both plans. Repeat each query three times; report individual timings without promising a speedup.

## Acceptance checks

- Results agree before and after indexing, including quality.
- Your plan annotation identifies estimated rows, actual rows, loops and sorting.
- You distinguish returned-row limits from work limits.

## Stretch and reflection

Compare a covering index with the primary key. What extra writes and storage would its additional columns require?

Save your SQL, actual output, and one explanation in `student-work/sql/day57/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-9).

[Previous: Day 56](day56.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 58](day58.md)
