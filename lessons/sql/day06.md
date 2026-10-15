# Day 06 — Group samples into accountable summaries

[Previous: Day 5](day05.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 7](day07.md)

**Week 1 · 45–75 minutes.** Prerequisites: days 1–5, or equivalent skills.

## Goal

Build grouped counts, distinguish `WHERE` from `HAVING`, and check that a summary accounts for every stored sample without combining incompatible quantities.

## Before you start

Review yesterday's quality policy and the difference between counting rows and values. A grouped result changes grain. A row that previously meant one observation can become one site total or one role total. Write that new meaning above each saved query.

## Concept

`GROUP BY` divides input rows into groups with equal key values. Aggregate functions then produce one result per group. Every selected expression must be a grouping expression, an aggregate, or otherwise allowed by PostgreSQL's grouping rules. Start with explicit grouping columns so the report's meaning stays clear.

`WHERE` filters input rows before grouping. `HAVING` filters completed groups using conditions such as a count threshold. Moving a condition between them can change the question. A count of all stored rows and a count of usable values are both useful, but they are different measures.

## Tiny example

```sql
SELECT role, count(*) AS stored_rows
FROM course.history
GROUP BY role
HAVING count(*) < 1728
ORDER BY role;
```

This returns one role: `duct_static`, with `1726` rows. The threshold comes from three points multiplied by 576 expected instants per point. It is a fixture expectation, not a rule for arbitrary buildings. This query identifies a short history; it does not identify the two missing instants.

## SQL challenge

Create a stored-row count per site and a stored/non-null count per role. Predict the site counts before executing. Add a third report with one row per site and temperature role, containing usable-row count and average in degrees Celsius. Apply the quality filter before grouping. Do not average all roles together.

Save an explanation of the grain of each report. A total across groups should be meaningful: site row counts partition the fixture, while role averages cannot simply be summed into a building temperature.

## Experiment

Count rows per quality using all samples. Then apply `WHERE quality = 'good'` and compare. The complete result has 24,189 good rows and one bad row. Use `HAVING count(*) > 1` to see how filtering groups differs from selecting individual good rows. Explain why a group can disappear entirely.

## Acceptance checks

- Site totals are 16,126 for `SYN-NORTH` and 8,064 for `SYN-SOUTH`, summing to 24,190.
- The role summary reveals the pressure shortfall and the power null separately.
- Temperature averages use degrees Celsius and exclude unusable values.

## Stretch and reflection

Group by both site and quality. Compare the result's grain with grouping by site alone. Which report would help investigate the bad row? Which helps reconcile storage totals? Keep result sets and interpretation together, and read [week 1 references](SOURCES.md#week-1) for grouping rules.

[Previous: Day 5](day05.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 7](day07.md)
