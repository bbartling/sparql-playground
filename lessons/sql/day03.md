# Day 03 — Filter rows with explicit logic

[Previous: Day 2](day02.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 4](day04.md)

**Week 1 · 45–75 minutes.** Prerequisites: days 1–2, or equivalent skills.

## Goal

Use `WHERE`, comparisons, `AND`, `OR`, and parentheses to request a precise subset of point metadata. Translate an English requirement into a condition you can explain.

## Before you start

Open the course `psql` client. Revisit yesterday's distinction between point identity and equipment label. Today's queries inspect metadata only; a point's role describes what it measures, while its unit describes the scale of its numeric values.

## Concept

`WHERE` keeps rows for which its condition is true. Text comparisons use single-quoted values: `site_id = 'SYN-NORTH'`. The expression `role = 'sat'` compares the role column to a text literal. Writing a column name inside single quotes would instead create a constant string.

`AND` requires both conditions; `OR` accepts either. PostgreSQL evaluates `AND` before `OR`. Parentheses make your intended grouping visible, including to your future self. A logically valid query can still answer the wrong question if its grouping is wrong. `IN` is a compact way to test membership in a short set of values.

## Tiny example

```sql
SELECT point_id, site_id, role, unit
FROM course.point
WHERE site_id = 'SYN-NORTH'
  AND role IN ('duct_static', 'duct_static_sp');
```

Expect four rows: two pressure roles for each of the two northern AHUs. Every returned unit is `Pa`. The query does not select equipment by its human label and does not read sample histories.

## SQL challenge

Write a query for northern points whose role is either `sat` or `sat_sp`, showing point identity, equipment identity, role, and unit. Write another for all southern points. Before running them, predict the row counts from the fixture inventory. Then write the first requirement a second way using `OR` with explicit parentheses.

Describe why the two versions express the same membership condition. Treat your expected counts as checks, not values to hardcode into the query.

## Experiment

Compare these predicates in otherwise identical queries:

```sql
WHERE site_id = 'SYN-NORTH' AND role = 'sat' OR role = 'sat_sp'
```

```sql
WHERE site_id = 'SYN-NORTH' AND (role = 'sat' OR role = 'sat_sp')
```

The first returns five rows, including the southern SAT setpoint; the second returns four. Find the extra row by inspecting its site and role. Explain the result using the grouping rules rather than the order of the written words.

## Acceptance checks

- The northern SAT pair returns 4 rows; the southern inventory returns 14.
- The membership and parenthesized `OR` versions select identical point identities.
- Your explanation accounts for the fifth row in the deliberately ambiguous example.

## Stretch and reflection

Filter roles with `unit = 'degC'` and inspect the result. Does knowing a unit tell you which physical quantity a point represents? Explain why SAT, outdoor temperature, and zone temperature need distinct roles despite sharing a unit. See [week 1 references](SOURCES.md#week-1) for Boolean expressions and comparisons.

[Previous: Day 2](day02.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 4](day04.md)
