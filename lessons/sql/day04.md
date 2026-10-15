# Day 04 — Order results and take a bounded look

[Previous: Day 3](day03.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 5](day05.md)

**Week 1 · 45–75 minutes.** Prerequisites: days 1–3, or equivalent skills.

## Goal

Create predictable report orderings and inspect a small sample of a large table without confusing the displayed rows with the entire dataset.

## Before you start

Connect to the course database and review the grain of `course.sample`: one row per site, point identity, and instant. The long table stores many roles in the same `value` column. Units live with point metadata; a naked value is not yet an interpretable engineering measurement.

## Concept

`ORDER BY` requests an ordering. `ASC` means ascending and `DESC` descending. Multiple expressions break ties from left to right. If your final ordering expressions still tie, the order within those ties is unspecified. `LIMIT` bounds returned rows after sorting, and it does not change what exists in the table.

A request for the first ten samples needs a definition of first. A timestamp alone is insufficient here because forty-two points usually share each timestamp. Include identities to make a stable selection. A small displayed result is useful for inspection; it cannot establish the maximum, minimum, or quality of an entire history.

## Tiny example

```sql
SELECT site_id, point_id, ts, value, quality
FROM course.sample
ORDER BY ts, site_id, point_id
LIMIT 5;
```

This returns five rows at `2026-01-05 00:00:00+00` when the client session uses UTC. All five have distinct point identities. Their numeric values can have different units, so do not average this mixed-role excerpt.

Use `SHOW timezone;` to inspect the display setting. We will study timestamp types and windows in week 3.

## SQL challenge

Produce a complete equipment inventory ordered by site ID, then label, then equipment ID. Produce the ten most recent raw samples with a deterministic ordering, showing their identifying columns and quality. Save both statements and explain which ordering direction you selected for each column.

Make a third report listing point roles and units in alphabetical order with point identity as the final tie breaker. Keep all forty-two rows for this inventory.

## Experiment

Run the tiny example with `LIMIT 1`, then `LIMIT 8`. Observe that a limit changes the number of displayed rows. Reverse only the timestamp direction and predict the earliest timestamp in the result. The fixture's final instant is `2026-01-06 23:55:00+00`. Explain why `LIMIT 5` without an order would not mean latest five.

## Acceptance checks

- Your equipment inventory contains three rows in a declared, repeatable order.
- Your latest-sample excerpt contains ten rows from the final fixture instant.
- Your report keeps enough identity columns to distinguish ties and enough context to avoid interpreting mixed units.

## Stretch and reflection

Explore `OFFSET 5 LIMIT 5` with the same deterministic ordering. What happens to page boundaries if a new earlier row arrives between page requests? Record the limitation without building an application paginator. Read [week 1 references](SOURCES.md#week-1) for sorting and limiting behavior.

[Previous: Day 3](day03.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 5](day05.md)
