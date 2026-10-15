# Day 29 — Measure quality before calculating performance

[Previous: Day 28](day28.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 30](day30.md)

**Week 5 · 45–75 minutes.** Prerequisites: Days 1–28, or equivalent SQL skills.

## Goal

Separate expected samples, received rows and usable measurements before reporting HVAC coverage.

## Before you start

Use the disposable `brickts_course` database from [the lab guide](LAB_GUIDE.md). Run `uv run python lessons/sql/lab.py check`. Read [the fixture contract](CONTRACT.md); keep the main fixture unchanged. Today's reporting window is `[2026-01-05 00:00Z, 2026-01-07 00:00Z)`.

## Concept

The grain of `course.sample` is one point at one instant within one site. A missing row and a present row with a null value are different observations. Quality describes whether a received value may enter a calculation. This course accepts only `quality = 'good' AND value IS NOT NULL`.

At five minute cadence, each point has 576 expected instants in the window. A ratio using received rows measures something different from a ratio using those 576 expected instants. Write the denominator beside every percentage. A missing record cannot be counted by filtering existing records alone; start from the expected point/time grid or an independently calculated expectation.

## Tiny example

```sql
SELECT count(*) AS received,
       count(value) AS nonnull,
       count(*) FILTER (WHERE quality = 'good' AND value IS NOT NULL) AS usable
FROM (VALUES (12.0, 'good'), (NULL, 'bad'), (9.0, 'bad')) AS v(value, quality);
```

Predict `3`, `2`, `1`. The bad numeric value explains why `count(value)` is insufficient.

## SQL challenge

Report each point's site, equipment UUID, role, expected count, received count, usable count and usable percentage. Use `course.point` as the inventory so a point with zero received rows would still appear. Keep counts as integers and percentages as numeric values with named units.

## Experiment

In a scratch `VALUES` relation, compare one absent sample, one bad/null sample and one bad numeric sample. Explain which totals distinguish all three. Do not insert these cases into `course.sample`.

## Acceptance checks

- Inventory has 42 points and 24,192 expected rows.
- Fixture has 24,190 received rows and 24,189 usable measurements.
- North Supply A has 574 received pressure samples and 575 usable power samples. Its power point still has 576 received rows.

## Stretch and reflection

Would a sensor reporting twice as frequently deserve twice the statistical weight? Explain why count coverage becomes inadequate when cadence changes.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day29/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-5) for exact language and domain details.

[Previous: Day 28](day28.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 30](day30.md)
