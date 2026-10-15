# Day 44 — Confirm consecutive candidates with gap-aware islands

[Previous: Day 43](day43.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 45](day45.md)

**Week 7 · 45–75 minutes.** Prerequisites: Days 1–43, or equivalent SQL skills.

## Goal

Require sustained evidence without joining observations across a missing interval.

## Before you start

Retain Day 43's complete evaluation stream, including false and unknown rows. Today's convention confirms the third consecutive eligible true observation, then later true observations in that same run. It does not backdate confirmation to the first candidate.

## Concept

A run starts when the current row is true and the preceding row is not eligible true, or when the timestamp gap exceeds 300 seconds. Partition by site, equipment and rule. Use `LAG` to inspect the prior timestamp and prior state, then derive run boundaries and an island identifier in separate query stages. Count observations within each true island.

Filtering to true rows before identifying breaks can join candidates separated by normal or unavailable data. Gap checks also matter when an entire pivot row is absent. Three consecutive observations are a count-based policy; they do not automatically mean fifteen elapsed minutes of evidence. Here observations are five minutes apart and intervals are at most five minutes.

## Tiny example

```sql
SELECT ts, extract(epoch FROM ts - lag(ts) OVER (ORDER BY ts)) AS gap_seconds
FROM (VALUES ('2026-01-05 08:00Z'::timestamptz),
             ('2026-01-05 08:05Z'::timestamptz),
             ('2026-01-05 08:15Z'::timestamptz)) AS v(ts);
```

The last gap is 600 seconds, so a true run must restart even if every shown row is a candidate.

## SQL challenge

Add island identity, position within the true island and a confirmed flag to your pressure detail. Show both raw and confirmed interval seconds. Keep quality breaks and time-gap breaks auditable rather than storing only the final Boolean.

## Experiment

Use scratch candidates at 00:00, 00:05, 00:15, 00:20 and 00:25. Predict the first confirmed timestamp. Repeat with an explicit unknown row at 00:10 instead of an absent row.

## Acceptance checks

- Fixture candidates form two five-observation islands, separated by the pressure gap.
- Confirmed fixture starts occur at Jan 5 08:10Z and 08:45Z.
- Raw candidate time is 3,000 seconds; confirmed time is 1,800 seconds under this non-backdating convention.
- Scratch confirmation begins at 00:25; inserting an unknown break cannot increase confirmation.

## Stretch and reflection

Compare three observations with a ten-minute persistence timer. Under irregular cadence, what different events could each policy confirm?

Save SQL, actual output and a short interpretation in your own `student-work/sql/day44/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-7) for exact language and domain details.

[Previous: Day 43](day43.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 45](day45.md)
