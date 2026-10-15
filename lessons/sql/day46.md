# Day 46 — Bound the rule window and retrieve enough context

[Previous: Day 45](day45.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 47](day47.md)

**Week 7 · 45–75 minutes.** Prerequisites: Days 1–45, or equivalent SQL skills.

## Goal

Evaluate a requested reporting window consistently while retrieving only the finite history its policy requires.

## Before you start

Reuse the 300 second interval cap, three-observation confirmation and ten-minute startup delay. Distinguish the requested output window from the earlier input context used for computation.

## Concept

Filtering inputs to the reporting start before computing windows changes the first results. A confirmed candidate at 08:10 may depend on candidates at 08:00 and 08:05. Startup state and interval clipping also need preceding observations. Retrieve bounded context, evaluate in timestamp order, and trim output only after deriving state.

For these course policies, a conservative twenty-five-minute lookback covers ten minutes to establish warmup eligibility at the earliest needed candidate, ten minutes of confirmation history, and a possible five-minute predecessor for an arbitrary start inside an interval. This bound supports current eligibility; it does not promise reconstruction of the fan's true startup time when it began hours earlier. Avoid future observations when defining a causal confirmation flag. A next timestamp may bound interval coverage without providing future candidate evidence.

## Tiny example

```sql
SELECT report_start - interval '25 minutes' AS context_start
FROM (VALUES ('2026-01-05 08:12Z'::timestamptz)) AS v(report_start);
```

The acquisition start is 07:47Z, but reported intervals still begin no earlier than 08:12Z.

## SQL challenge

Parameterize a bounded pressure report with start and end instants. Evaluate confirmation and startup from finite lookback, include the sample governing the start if eligible, and clip durations to the requested half-open window. Reject an end that is not later than start. Keep SQL values bound when called from a program.

## Experiment

Compare `[08:10Z,08:20Z)` with `[08:12Z,08:18Z)` on Jan 5 for north Supply A. Then run a longer enclosing window and compare its clipped detail with the short-window result. Predict equality before executing.

## Acceptance checks

- The aligned ten-minute window has 600 confirmed seconds; the inside-interval six-minute window has 360.
- Context rows never inflate the output duration.
- Short-window confirmation agrees with the same instants from the enclosing report.
- SQL has explicit bounds and does not scan unlimited history to infer startup.

## Stretch and reflection

If confirmation changes to ten observations or an hour-long delay, which lookback bound must change? Record that relationship alongside the policy version.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day46/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-7) for exact language and domain details.

[Previous: Day 45](day45.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 47](day47.md)
