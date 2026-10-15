# Day 31 — Distinguish fan command from observed status

[Previous: Day 30](day30.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 32](day32.md)

**Week 5 · 45–75 minutes.** Prerequisites: Days 1–30, or equivalent SQL skills.

## Goal

Define an auditable fan operating state, including disagreement and unavailable evidence.

## Before you start

Inspect `course.point` roles and units. The fixture contains `fan_status` and `fan_speed_pct`; it has no independent binary fan command point. A speed percentage is a requested operating signal only when the adapter explicitly assigns that meaning.

## Concept

A command describes intent; status describes reported operation. Neither proves airflow. For this teaching policy, eligible binary status takes precedence: `1` means on, `0` means off. If status is unavailable, retain unknown for observed runtime. A separate command-based estimate can be reported with a different name. Do not silently replace missing status with speed or turn null into off.

Treat a disagreement as evidence worth preserving. An on command with off status could indicate a delayed start, a safety trip, a mapping error or stale data. SQL alone cannot choose among those explanations. State values outside the declared binary domain are invalid, even when quality says good.

## Tiny example

```sql
SELECT status, command,
       CASE WHEN status = 1 THEN 'on'
            WHEN status = 0 THEN 'off'
            ELSE 'unknown' END AS observed_state
FROM (VALUES (0, 1), (1, 0), (NULL, 1)) AS v(status, command);
```

This three-row example is deliberately independent of the fixture. Its states are off, on and unknown; the first two rows also disagree with command.

## SQL challenge

Create a state projection over `course.ahu_5m`, retaining site, equipment UUID and timestamp. Name your status validity rule. Add a separate speed-request indicator using a threshold you declare, without presenting it as measured runtime. Count observed on, off, unknown and command/status disagreements per equipment.

## Experiment

Construct scratch rows for status `NULL`, `2`, `0` and `1`, paired with speed values below, at and above your threshold. Predict the classification at the threshold. Compare policies using `>` and `>=`.

## Acceptance checks

- Binary status produces no unknown fixture states.
- Both sites' equipment called Supply A remain distinct.
- Scratch missing or invalid status stays unknown; disagreement is visible.
- Your report names which signal supports observed operation and which supports an estimate.

## Stretch and reflection

What evidence would you require before using current, differential pressure or speed feedback as a runtime proxy? Record one failure mode for each possible substitute.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day31/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-5) for exact language and domain details.

[Previous: Day 30](day30.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 32](day32.md)
