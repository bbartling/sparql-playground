# Day 40 — Read the shape of fan and temperature relationships

[Previous: Day 39](day39.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 41](day41.md)

**Week 6 · 45–75 minutes.** Prerequisites: Days 1–39, or equivalent SQL skills.

## Goal

Evaluate HVAC relationships without confusing an algebraic illustration with a calibrated equipment model.

## Before you start

Inspect the units and ranges of `fan_speed_pct`, `kw`, `sat`, `sat_sp` and `cooling_pct`. Keep fan-off rows, startup behavior and missing values distinguishable in your scratch output.

## Concept

A fan affinity-law illustration says power scales approximately with the cube of speed under suitable comparable conditions. Real systems also have static pressure control, changing resistance, minimum power and equipment efficiency. A percentage command is not guaranteed to be measured speed. Use the cube calculation as an explicitly assumed reference, not a production prediction fitted from these two days.

Supply-air temperature error is `sat - sat_sp` in °C; it is not a percentage. A larger cooling command can accompany a larger temperature error because the controller is responding to a load. That association alone does not show that cooling caused the error. Preserve operating context when preparing comparisons.

## Tiny example

```sql
SELECT speed_pct, 12.0 * power(speed_pct / 100.0, 3) AS illustrative_kw
FROM (VALUES (50.0), (100.0)) AS v(speed_pct);
```

Under that stated 12 kW full-speed illustration, 50% speed yields 1.5 kW. Those assumptions are not fixture calibration results.

## SQL challenge

Create fan-on scatter rows for speed-versus-kW and cooling-command-versus-SAT-error. Include equipment, timestamp, units and valid seconds. Compare per-equipment summaries with an all-equipment summary. Explain whether the fixture contains enough speed variation to estimate a meaningful curve; a constant input cannot identify one.

## Experiment

Build scratch observations with two equipment operating at different fixed power levels and different temperatures. Compare a pooled trend with within-equipment variation. Explain how equipment identity can create a misleading apparent relationship even when each individual series is constant.

## Acceptance checks

- The tiny calculation returns 1.5 and 12 kW, with its assumptions stated.
- Temperature error retains a °C unit; commands retain percent units.
- North Supply B's warm SAT interval is visible on Jan 5 12:00–13:00Z.
- Your interpretation distinguishes a relationship, an illustrative model and evidence of a fault.

## Stretch and reflection

What additional data and controlled comparisons would make a fan power model defensible? Identify one useful validation window that differs from a fitting window.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day40/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-6) for exact language and domain details.

[Previous: Day 39](day39.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 41](day41.md)
