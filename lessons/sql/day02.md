# Day 02 — Read tables and name the row

[Previous: Day 1](day01.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 3](day03.md)

**Week 1 · 45–75 minutes.** Prerequisites: days 1–1, or equivalent skills.

## Goal

Read metadata tables with `SELECT`, choose useful columns, and state what one returned row represents. This is the first step toward trusting a report.

## Before you start

Connect using `uv run python lessons/sql/lab.py psql`. Keep [the lab guide](LAB_GUIDE.md) available. The fixture has two synthetic sites, three AHUs, and fourteen measured roles per AHU. An AHU is an air handling unit; no HVAC expertise is required for today's inventory queries.

## Concept

A table contains rows described by named columns. A query selects columns from an input relation. Its result is another relation, not necessarily a stored table. The grain is the meaning of one row: `course.site` has one row per site, `course.equipment` one per equipment identity, and `course.point` one per measured point identity.

The schema prefix in `course.site` tells PostgreSQL which namespace contains the table. Use qualified names throughout the course so a similarly named table elsewhere cannot change your query accidentally. A UUID is an opaque identity value. Copy it when needed; do not reconstruct it from a friendly label. North and south both contain an AHU labeled `Supply A`.

## Tiny example

```sql
SELECT site_id, label, tz
FROM course.site;

SELECT equipment_id, site_id, label, kind
FROM course.equipment;
```

The first result has two rows, including site IDs `SYN-NORTH` and `SYN-SOUTH`. The second has three rows. Row order is unspecified until you ask for an order; an apparent order in one run is not a promise.

In `psql`, `\d course.point` shows column definitions without reading sample values. `SELECT *` is useful for a quick inspection, but an explicit report should list its columns so its shape remains deliberate.

## SQL challenge

Create three inventory statements: site IDs and labels; equipment identities, labels, and site IDs; point identities, roles, and units. Add understandable output aliases to at least one statement. Write a sentence describing each result's grain. Check the point inventory has forty-two rows, with roles such as `duct_static` in Pa and `kw` in kW.

## Experiment

Select only `label` from `course.equipment`. Then select `equipment_id, site_id, label`. Compare what a reader can identify in each result. Why can two matching labels refer to different equipment? Try swapping selected column order; explain why this changes presentation without changing equipment identities.

## Acceptance checks

- Your inventories contain 2 site rows, 3 equipment rows, and 42 point rows.
- You can identify the same equipment even when its label is hidden.
- Every saved query names its source schema and has a stated row meaning.

## Stretch and reflection

Inspect `course.sample` with `\d`, without printing its entire contents. Its row represents a point at an instant within a site. Which columns appear necessary to distinguish two measurements? Record your hypothesis; keys are studied next week. Consult [week 1 references](SOURCES.md#week-1) for `SELECT` and `psql` details.

[Previous: Day 1](day01.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 3](day03.md)
