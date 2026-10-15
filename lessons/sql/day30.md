# Day 30 — Turn irregular samples into bounded intervals

[Previous: Day 29](day29.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 31](day31.md)

**Week 5 · 45–75 minutes.** Prerequisites: Days 1–29, or equivalent SQL skills.

## Goal

Calculate observed seconds without carrying one measurement through an arbitrarily long outage.

## Before you start

Keep Day 29's quality policy and half-open window. Save a separate interval query; later runtime, energy and fault reports will reuse its declared convention.

## Concept

A sample is an instant. Duration is an interpretation. For this course, a sample's value represents the interval beginning at its timestamp and ending at the earliest of the next sample, 300 seconds later, or the reporting end. Clip its beginning to the reporting start. Only positive intervals contribute. Partition `lead(ts)` by site and point and order by time; crossing a point boundary creates meaningless durations.

Choose the immediate next received timestamp before excluding bad rows. A bad observation ends the earlier observation's authority and starts unknown time. When a window begins between observations, inspect a predecessor up to 300 seconds before the start; filtering to the window before computing intervals loses that possible coverage. Absence beyond the cap remains unknown.

## Tiny example

```sql
SELECT ts, lead(ts) OVER (ORDER BY ts) AS next_ts
FROM (VALUES ('2026-01-05 08:20Z'::timestamptz),
             ('2026-01-05 08:35Z'::timestamptz)) AS v(ts);
```

The first successor is fifteen minutes away. Under the five minute cap, its covered interval ends at 08:25, leaving ten minutes unknown.

## SQL challenge

Build intervals for north Supply A's `duct_static` point using its discovered UUID. Return interval start, end, duration seconds and eligibility. Calculate valid coverage and unknown seconds for the 48 hour window. Keep the last sample's bounded tail; a null `lead` does not automatically mean zero duration.

## Experiment

Use three scratch timestamps at 00:00, 00:02 and 00:12. Predict bounded coverage for `[00:01,00:13)` before running. Compare a 300 second cap with unrestricted forward fill and explain the difference.

## Acceptance checks

- Full fixture pressure coverage is 47 hours 50 minutes, with 600 unknown seconds.
- No interval lasts more than 300 seconds; adjacent intervals do not overlap.
- Moving the window boundary inside a valid interval clips that interval accurately.

## Stretch and reflection

How would a counter, an instantaneous flow measurement and a discrete status differ in their appropriate interpolation policy? Keep today's policy explicit rather than assuming it is universal.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day30/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-5) for exact language and domain details.

[Previous: Day 29](day29.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 31](day31.md)
