# Day 17 — Add window calculations without collapsing rows

[Previous: Day 16](day16.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 18](day18.md)

**Week 3 · 45–75 minutes.** Prerequisites: days 1–16, or equivalent skills.

## Goal

Use `OVER`, `PARTITION BY`, and ordering to add context to individual observations. Distinguish a window calculation from a grouped summary.

## Before you start

Review the grain of `course.history`. A pressure history contains one observation per point and instant. Partitioning by site and point keeps independent sensors separate even when timestamps and roles match.

## Concept

`GROUP BY` collapses rows into one output per group. A window function calculates across a related set of rows while retaining each input row. `PARTITION BY` chooses independent populations. `ORDER BY` inside `OVER` defines the order used by functions such as `row_number`; it is separate from the final result's display order.

A window aggregate without an internal ordering, such as `count(*) OVER (PARTITION BY ...)`, can provide a full-partition count on every observation. Adding an ordering changes the default frame for many aggregates, often producing a running calculation. State the frame explicitly when learning running calculations, and do not assume every `OVER` clause means the same population.

## Tiny example

```sql
SELECT site_id, point_id, ts,
       row_number() OVER (
           PARTITION BY site_id, point_id ORDER BY ts
       ) AS observation_number,
       count(*) OVER (
           PARTITION BY site_id, point_id
       ) AS point_stored_rows
FROM course.history
WHERE role = 'duct_static'
ORDER BY site_id, point_id, ts
LIMIT 8;
```

The excerpt still has observation grain. Across the full result, one point's stored-row count is 574 and the other two are 576. The displayed point depends on UUID ordering; inspect all three deliberately before drawing a conclusion.

## SQL challenge

Use a CTE to number power observations within each site and point. Return the first and last observation from every point with its original timestamp, value, and quality. Do not choose a point by the smallest UUID or combine multiple points into one partition.

Produce a separate grouped count for each power point and reconcile it with the window partition counts. All three have 576 stored rows even though one has an unusable value. Explain why row numbering does not repair that measurement.

## Experiment

Remove `point_id` from the partition and inspect a bounded excerpt. Several power points now share a site population, and equal timestamps create ties. Identify why row numbers no longer mean position within one sensor history. Restore the intended partition and order.

Compare a full-partition count with an explicitly running `count(*) OVER (PARTITION BY site_id, point_id ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`. Predict each value at the third observation.

## Acceptance checks

- First/last reports retain identities and return six power rows in total.
- Counts and row numbers have different meanings you can explain.
- Your partitions preserve individual point histories and your final output order is explicit.

## Stretch and reflection

Why must a deterministic tie breaker be added if ordering columns are not unique? Read [week 3 references](SOURCES.md#week-3) for window frames and function behavior.

[Previous: Day 16](day16.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 18](day18.md)
