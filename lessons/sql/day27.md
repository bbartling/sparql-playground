# Day 27 — Turn assumptions into reviewable SQL checks

[Previous: Day 26](day26.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 28](day28.md)

**Week 4 · 45–75 minutes.** Prerequisites: days 1–26, or equivalent skills.

## Goal

Write small SQL checks that distinguish fixture expectations from general data contracts, and collect evidence another person can interpret without guessing what “pass” means.

## Before you start

Keep your schema notebook, join report, coverage report, and migration notes available. Today's checks read `course` and may use scratch data for intentional failures. A failed course check should trigger investigation, not a change to the expected number just to obtain green output.

## Concept

An invariant is a rule that must hold, such as a sample referencing a point in the same site. A fixture expectation describes this particular seed, such as having exactly forty-two points. Both are useful, but they have different lifetimes. Legitimate new equipment should change fixture totals while preserving relationship integrity.

A check needs a named question, expected outcome, actual outcome, and failure interpretation. Some checks return a Boolean row; others list violations and pass when that list is empty. Document which convention you use. A query that prints nothing because it failed to run is not a passing empty result.

## Tiny example

```sql
WITH checks AS (
    SELECT 'site_count' AS check_name, 2::bigint AS expected,
           count(*) AS actual
    FROM course.site
    UNION ALL
    SELECT 'point_count', 42::bigint, count(*)
    FROM course.point
    UNION ALL
    SELECT 'sample_count', 24190::bigint, count(*)
    FROM course.sample
)
SELECT check_name, expected, actual, actual = expected AS passed
FROM checks
ORDER BY check_name;
```

All three fixture checks should return true after a fresh load. They prove totals, not correct joins, units, quality handling, or time support.

## SQL challenge

Create a report-contract file with checks for inventory totals, the single bad/null value, uniqueness of the joined logical observation key, and site-consistent sample-to-point relationships. Include at least one check on a summary's grain or quality policy. State whether each check is fixture-specific or intended as a lasting invariant.

For join uniqueness, a violation query can group by `(site_id, point_id, ts)` and return groups with `count(*) > 1`. Run it against the same joined relation your report actually uses, not only the base table that already has a key.

## Experiment

Use a small scratch dataset to make one contract check fail deliberately. Suitable cases include duplicate joined rows or a report population containing an unusable measurement. Record the failing evidence, fix the scratch report, and observe the check pass. Keep the fixture untouched.

## Acceptance checks

- Your fixture totals are 2 sites, 42 points, and 24,190 samples.
- Every check has a clear expected outcome and explains its failure meaning.
- One deliberate scratch failure demonstrates that the checks can detect a real report mistake.

## Stretch and reflection

Run `uv run python lessons/sql/lab.py check` from the repository root and keep its actual status with your SQL evidence. Explain what your report checks add beyond fixture loading checks. Read [week 4 references](SOURCES.md#week-4) for constraints and transaction behavior.

[Previous: Day 26](day26.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 28](day28.md)
