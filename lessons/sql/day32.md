# Day 32 — Calculate runtime with SQL and explicit unknown time

[Previous: Day 31](day31.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 33](day33.md)

**Week 5 · 45–75 minutes.** Prerequisites: Days 1–31, or equivalent SQL skills.

## Goal

Sum observed fan-on seconds while keeping off time and unavailable time visible.

## Before you start

Reuse the bounded interval convention from Day 30 and the state policy from Day 31. Use UTC for today's full 48 hour report, with duration expressed in seconds and hours.

## Concept

Runtime is the sum of eligible interval seconds whose observed state is on. It is not generally the count of on rows divided by twelve. That shortcut works only when every selected row represents exactly five minutes, with correct edges and no duplicates or quality gaps.

The reporting grain is one equipment and window. On, off and unknown seconds should reconcile to the window's duration. Unknown means the available evidence does not support either state. A schedule describes intended hours; it is a separate quantity even when it matches the fixture's observed status.

## Tiny example

```sql
SELECT sum(seconds) FILTER (WHERE state = 'on') / 3600.0 AS on_hours,
       sum(seconds) FILTER (WHERE state = 'unknown') AS unknown_seconds
FROM (VALUES ('on', 120), ('on', 300),
             ('off', 300), ('unknown', 180)) AS v(state, seconds);
```

The two on intervals total seven minutes. Counting each as five minutes would overstate runtime.

## SQL challenge

Produce one runtime row per equipment using eligible `fan_status` intervals. Include site and equipment identity, requested window boundaries, on/off/unknown seconds, hours and valid coverage percentage. Compare observed hours with the contract's scheduled hours in a separately labelled column.

## Experiment

Repeat for `[2026-01-05 05:58Z, 2026-01-05 06:07Z)` on north Supply A. Account for the predecessor and the window end. Predict two off minutes and seven on minutes. Explain why merely selecting sample timestamps within the window loses information.

## Acceptance checks

- Over the 48 hour fixture: north Supply A has 24 on hours, north Supply B 12, and south Supply A 12.
- Each equipment has zero unknown status seconds and 48 total classified hours.
- The partial-window experiment reconciles to nine minutes.
- Empty on time is represented as zero; unavailable data remains separately identifiable.

## Stretch and reflection

Would resetting a controller counter or losing a status sensor change the schedule? Explain how your output prevents those separate facts from being conflated.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day32/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-5) for exact language and domain details.

[Previous: Day 31](day31.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 33](day33.md)
