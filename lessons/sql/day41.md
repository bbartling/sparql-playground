# Day 41 — Save query results without hiding freshness or detail

[Previous: Day 40](day40.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 42](day42.md)

**Week 6 · 45–75 minutes.** Prerequisites: Days 1–40, or equivalent SQL skills.

## Goal

Distinguish a view, a materialized summary and a plot-ready result, with explicit refresh and lineage.

## Before you start

Use only the `student` schema for objects you create. Pick one completed daily report and its bounded source window. Keep the SQL text alongside any stored results.

## Concept

A PostgreSQL view reruns its query when read. A materialized view stores a result and changes only when refreshed. A table created from a query is also a snapshot, with no automatic connection to later source changes. These behaviors matter when a dashboard looks current but its numbers describe an older extract.

A summary row per equipment/day and a scatter row per equipment/interval serve different purposes. Storing just means loses individual points, weights and exclusions needed to reconstruct a plot or examine a surprising hour. A summary should carry numerator, denominator, quality counts, window, policy version and a refresh/as-of record appropriate to its use. No metadata column by itself guarantees freshness; the refresh procedure must maintain it.

## Tiny example

```sql
CREATE MATERIALIZED VIEW student.day41_inventory AS
SELECT site_id, count(*) AS equipment_count
FROM course.equipment
GROUP BY site_id;
```

This stores two inventory rows. `REFRESH MATERIALIZED VIEW student.day41_inventory;` reruns the defining query. This ordinary PostgreSQL feature is not a Timescale continuous aggregate.

## SQL challenge

Materialize one bounded comfort or energy summary in `student`, preserving enough sums and weights to reconcile it. Keep a separate detail query for the corresponding scatter dataset. Write a short refresh procedure and an explicit statement of what the summary cannot reconstruct.

## Experiment

Use a tiny scratch source table and materialized view. Insert a scratch source row, query the stored result, refresh, then query again. Predict both results. Do not mutate the course fixture merely to demonstrate staleness.

## Acceptance checks

- The inventory example has counts two for north and one for south.
- Your scratch experiment visibly demonstrates stored-result staleness and refresh.
- Summary totals reconcile to the original detail query.
- The report records source window, policy and as-of evidence; a summary row is never offered as a scatter observation.

## Stretch and reflection

Which source or policy changes require recomputation? Explain how you would detect that a stored result was produced with an obsolete quality policy.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day41/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-6) for exact language and domain details.

[Previous: Day 40](day40.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 42](day42.md)
