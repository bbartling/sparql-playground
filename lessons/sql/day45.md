# Day 45 — Gate rules by mode and allow startup time

[Previous: Day 44](day44.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 46](day46.md)

**Week 7 · 45–75 minutes.** Prerequisites: Days 1–44, or equivalent SQL skills.

## Goal

Exclude expected startup behavior without using a fixed clock time as a substitute for operating history.

## Before you start

The fixture has no general heating/cooling operating-mode column. Today uses a declared fan-on evaluation mode and synthetic scratch mode labels. Keep those labels separate from measured fixture roles.

## Concept

Rule applicability can change with operating mode. A supply-air cooling rule needs a cooling context; an economizer rule may need adequate outdoor/return temperature separation and an enabled economizer. Filling absent mode information with a convenient default invents evidence.

For the pressure exercise, add a ten-minute fan startup delay. Derive continuous on history from observed status transitions and break it on off, unknown or an excessive gap. Evaluate only when at least ten minutes of continuous eligible on evidence are known. At the start of a dataset, an already-on fan has an unknown actual start; a sufficiently long observed on stretch can establish a lower bound on runtime. Record that convention.

## Tiny example

```sql
SELECT now_ts - startup_ts >= interval '10 minutes' AS warmup_complete
FROM (VALUES ('2026-01-05 06:10Z'::timestamptz,
              '2026-01-05 06:00Z'::timestamptz)) AS v(now_ts, startup_ts);
```

At exactly ten minutes, the stated `>=` policy allows evaluation. That boundary choice belongs in rule metadata.

## SQL challenge

Add mode eligibility, continuous-on age or lower bound, warmup eligibility and exclusion reason to your pressure detail. Preserve the raw teaching comparison separately from the mode-gated candidate. Confirm candidates only after applying the gate.

## Experiment

Create a scratch startup with low pressure for the first ten minutes and normal pressure afterward. Compare results with and without the gate. Add one unknown status interval in the middle; predict how it affects your known continuous-on history.

## Acceptance checks

- North Supply A's Jan 5 06:00Z startup is excluded until 06:10Z under the declared policy.
- Its 08:00Z pressure excursion remains eligible; the warmup gate does not erase it.
- Unknown startup history is visible rather than guessed from a schedule.
- Scratch missing mode or status cannot create a confirmed fault.

## Stretch and reflection

How could repeated short fan cycles interact with this delay? Describe a separate cycling metric without weakening the pressure rule's declared startup policy.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day45/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-7) for exact language and domain details.

[Previous: Day 44](day44.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 46](day46.md)
