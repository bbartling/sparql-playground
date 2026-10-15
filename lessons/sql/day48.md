# Day 48 — Preserve raw evidence beside confirmed fault summaries

[Previous: Day 47](day47.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 49](day49.md)

**Week 7 · 45–75 minutes.** Prerequisites: Days 1–47, or equivalent SQL skills.

## Goal

Design fault detail and summaries that a reviewer can trace back to input measurements and time policies.

## Before you start

Reuse your pressure predicate, startup gate and confirmation convention. Read the distinction between teaching SQL and production rule behavior in [the bridge notes](OPENFDD_BRIDGE.md).

## Concept

Raw candidate, confirmed condition, confirmed duration and event count are different outputs. A Boolean at one timestamp is not an event count. Summing Boolean values counts observations; summing bounded interval seconds measures duration. Two separate confirmed runs can have the same total seconds as one longer run.

Retain detail at equipment/rule/evaluation-time grain: input values and validity, state, threshold, raw Boolean, exclusion reason, run identity, confirmation position, confirmed flag, interval seconds and policy identity. A summary can then aggregate counts and seconds without losing the ability to explain a surprising result. Name unavailable and excluded duration separately from evaluated false duration.

## Tiny example

```sql
SELECT count(*) FILTER (WHERE confirmed) AS confirmed_observations,
       sum(seconds) FILTER (WHERE confirmed) AS confirmed_seconds
FROM (VALUES (true, 300), (true, 120), (false, 300)) AS v(confirmed, seconds);
```

The results are two observations and 420 seconds. Neither number alone says how many events occurred.

## SQL challenge

Create separate scratch detail and summary views for your bounded pressure report. Summarize raw seconds, confirmed seconds, confirmed island count, unknown seconds and eligible coverage by site/equipment/rule. Preserve enough keys to select all detail for one event without matching by equipment label.

## Experiment

Compare two synthetic datasets with identical confirmed seconds: one continuous run and two separated runs. Demonstrate that event counts differ. Then shorten the final interval and show that duration changes while the number of confirmed observations may not.

## Acceptance checks

- Fixture north Supply A has 3,000 raw seconds and 1,800 confirmed seconds across two confirmed islands under the three-observation policy.
- The ten-minute pressure gap is unknown, not an event or a pass.
- Summary duration exactly reconciles to detail interval seconds.
- Output says `confirmed_seconds`; it does not label that number simply `faults`.

## Stretch and reflection

Which detail would you include in an operator-facing explanation? Choose a compact evidence set that supports review without implying the rule knows the physical root cause.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day48/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-7) for exact language and domain details.

[Previous: Day 47](day47.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 49](day49.md)
