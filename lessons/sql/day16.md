# Day 16 — Use CTEs to make query stages readable

[Previous: Day 15](day15.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 17](day17.md)

**Week 3 · 45–75 minutes.** Prerequisites: days 1–15, or equivalent skills.

## Goal

Break a report into named relational stages with a common table expression, or CTE. Explain each stage's grain and verify that an early filter matches the report's question.

## Before you start

Review `WHERE`, grouping, and the good/non-null calculation policy. A CTE is introduced with `WITH`. It is available to the statement that follows; it does not create a durable table or a new stored copy of the fixture.

## Concept

A complicated query is easier to review when selection, quality filtering, and summary have clear names. Each CTE is a relation with named columns. A later stage can consume an earlier one. Names should describe the population or result, such as `usable_power`, rather than merely `step1`.

CTEs are a readability tool, not a guarantee that PostgreSQL executes each stage separately or that a query becomes faster. The optimizer can change the execution strategy. First ensure the statement answers the right question; execution plans come next week.

## Tiny example

```sql
WITH usable_power AS (
    SELECT site_id, point_id, ts, value
    FROM course.history
    WHERE role = 'kw'
      AND quality = 'good'
      AND value IS NOT NULL
)
SELECT site_id, count(*) AS usable_rows, avg(value) AS mean_kw
FROM usable_power
GROUP BY site_id
ORDER BY site_id;
```

The named stage has one row per usable power observation. The result has one row per site, with 1,151 usable rows at north and 576 at south. The average is a sample-weighted mean power across observations at that site; it is neither energy nor an equipment total.

## SQL challenge

Write a CTE report for temperature observations during Jan 5 UTC. Make the time selection and quality policy visible, then summarize by site, equipment identity, and role. Choose two temperature roles and show usable count and mean in degrees Celsius. State each stage's grain before executing.

Write a second CTE that counts stored observations per pressure point for that same day, then returns only short groups against the 288-row expectation. The affected pressure point should have 286 rows. Resolve its equipment through metadata after identifying its point identity.

## Experiment

Move the quality filter after a first summary in a draft. Can a grouped count still tell you which individual values were unusable if you discarded their quality field? Record the missing information. Compare with a design that preserves stored count and usable count as separate aggregates.

Inspect the CTE alone by temporarily selecting its named columns from it. Limit and order the inspection so your evidence is small and repeatable.

## Acceptance checks

- Your stages have explicit grains and do not mix incompatible units.
- The power demonstration returns usable counts 1,151 and 576.
- The Jan 5 pressure report finds one 286-row point and does not infer its identity from a label.

## Stretch and reflection

Create two related CTEs in one statement and explain their dependency. Which name makes a mistaken filter easier to notice? Read [week 3 references](SOURCES.md#week-3) for `WITH` scope and optimizer behavior.

[Previous: Day 15](day15.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 17](day17.md)
