# Day 05 — Count missing values before averaging

[Previous: Day 4](day04.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 6](day06.md)

**Week 1 · 45–75 minutes.** Prerequisites: days 1–4, or equivalent skills.

## Goal

Distinguish a missing row from a stored null value, and calculate an average only after stating the role, units, and quality policy.

## Before you start

Connect to the course database. Today uses `course.history`, a prepared view that joins sample rows to their point and equipment metadata. One view row still represents one stored sample. Inspect it with `\d course.history` before querying.

## Concept

SQL `NULL` represents an unknown or absent value. It is not numeric zero and not an empty string. Use `IS NULL` or `IS NOT NULL`; `value = NULL` does not test missingness. A comparison involving null usually evaluates to unknown, and `WHERE` keeps only true results.

`count(*)` counts rows. `count(value)` counts rows whose value is non-null. `avg(value)` ignores nulls but does not know whether a non-null value has good quality. The course's calculation policy is `quality = 'good' AND value IS NOT NULL`. State that policy explicitly. Missing rows never reach an aggregate; a count needs an expected population before it can reveal their absence.

## Tiny example

```sql
SELECT count(*) AS stored_rows,
       count(value) AS rows_with_value
FROM course.sample;

SELECT count(*) AS usable_temperature_rows,
       avg(value) AS mean_deg_c
FROM course.history
WHERE role = 'oat'
  AND quality = 'good'
  AND value IS NOT NULL;
```

The first query returns `24190` stored rows and `24189` non-null values. The second has 1,728 usable outdoor-temperature rows; its mean is in degrees Celsius. Treat the observed average as a result to record, not a universal outdoor temperature.

## SQL challenge

Count the stored null values and list their site, equipment label, role, timestamp, and quality through the history view. Count all `kw` rows and all usable `kw` rows separately. Explain why these counts differ by one. Write an average for one temperature role of your choice, and label its unit in the output alias.

## Experiment

Compare `WHERE value IS NULL` with `WHERE value = NULL` on `course.sample`. The first finds one row; the second finds none. Then count `duct_static` rows: 1,726 exist, although three complete five-minute point histories would contain 1,728. Explain why an `IS NULL` search cannot find the two absent pressure rows.

## Acceptance checks

- Your report distinguishes 1 stored bad/null sample from 2 entirely absent samples.
- `kw` has 1,728 stored rows and 1,727 usable rows.
- Every average has a named role, unit, and explicit quality filter.

## Stretch and reflection

Try `coalesce(value, 0)` only in a display query and explain how replacing unknown measurements with zero could bias an average. When is an explicit unknown label more honest? Consult [week 1 references](SOURCES.md#week-1) for null semantics and aggregate functions.

[Previous: Day 4](day04.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 6](day06.md)
