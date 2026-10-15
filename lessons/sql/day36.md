# Day 36 — Choose the denominator for comfort percentage

[Previous: Day 35](day35.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 37](day37.md)

**Week 6 · 45–75 minutes.** Prerequisites: Days 1–35, or equivalent SQL skills.

## Goal

Report temperature comfort as a clearly defined percentage with coverage and operating context.

## Before you start

Inspect `zone_temp`, `zone_temp_sp` and `fan_status` in `course.ahu_5m`. The fixture's teaching comfort band is 20–24 °C inclusive. This is an exercise policy, not a universal comfort or health standard.

## Concept

A percentage needs a numerator, denominator and eligibility policy. For all-time observed comfort, the numerator is eligible zone-temperature seconds inside the band and the denominator is all eligible zone-temperature seconds. Report unknown temperature seconds separately. For fan-on comfort, both temperature and status must be eligible and status must be on; the denominator changes accordingly.

A setpoint error metric answers another question: `zone_temp - zone_temp_sp` measures deviation from a target. A temperature can be close to its setpoint while outside a chosen comfort band. Keep band compliance, setpoint deviation and measurement availability as distinct columns.

## Tiny example

```sql
SELECT 100.0 * sum(seconds) FILTER (WHERE temp_c BETWEEN 20 AND 24)
       / NULLIF(sum(seconds), 0) AS observed_comfort_pct
FROM (VALUES (22.0, 300), (28.0, 60)) AS v(temp_c, seconds);
```

The result is about 83.33%, because five comfortable minutes and one uncomfortable minute have unequal weights. Averaging two row flags would report 50%.

## SQL challenge

Report all-time and fan-on comfort per equipment over the full fixture. Include comfortable seconds, eligible denominator seconds, unknown seconds, the named band and percentage. Define the output for an empty eligible denominator; null with an explanation is preferable to a fabricated 0% or 100%.

## Experiment

Use scratch rows at 19.9, 20, 24 and 24.1 °C. Predict inclusion before running. Add a missing temperature during fan-on time and show why removing it from both numerator and denominator also requires reporting coverage.

## Acceptance checks

- North Supply A has one uncomfortable hour: all-time comfort is approximately 97.9167%, and fan-on comfort approximately 95.8333%.
- The other equipment have 100% for both defined denominators.
- Inclusive boundaries pass; a zero denominator does not cause division by zero.
- Output makes fan-on and all-time percentages distinguishable without reading SQL.

## Stretch and reflection

What additional measurements would a formal comfort assessment need? Explain why this temperature-only teaching result must retain its limited name.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day36/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-6) for exact language and domain details.

[Previous: Day 35](day35.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 37](day37.md)
