# Day 37 — Use mixing mathematics with physical eligibility checks

[Previous: Day 36](day36.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 38](day38.md)

**Week 6 · 45–75 minutes.** Prerequisites: Days 1–36, or equivalent SQL skills.

## Goal

Calculate a teaching outdoor-air fraction and understand when its denominator makes the result unreliable.

## Before you start

Read units for `oat`, `rat`, `mat` and `damper_pct`. Temperatures are °C; damper position is a percentage signal. Query metadata rather than trusting an English column label.

## Concept

For an ideal two-stream sensible-temperature mixture, `mat = fraction × oat + (1 - fraction) × rat`. Rearranging gives `fraction = (mat - rat) / (oat - rat)`. This simplified relationship assumes representative, compatible measurements and adequate mixing. When outdoor and return temperatures are nearly equal, a tiny sensor error creates a large fraction error. Declare a minimum absolute temperature separation, such as 2 °C, as a teaching eligibility threshold.

A fraction outside 0–1 should remain visible as a diagnostic result. Clamping to 0–1 can hide sensor or model problems. Damper percentage is actuator position; it is not necessarily outdoor airflow fraction. Fan status and operating mode determine whether interpreting the mixture is useful.

## Tiny example

```sql
SELECT (18.0 - 24.0) / NULLIF(12.0 - 24.0, 0) AS outdoor_fraction;
```

The result is 0.5, or 50%. This example demonstrates the algebra, not a complete economizer diagnostic.

## SQL challenge

Using `course.ahu_5m`, report eligible fan-on intervals with return, outdoor and mixed-air temperature, separation, computed fraction and damper percentage. Give excluded rows a reason such as missing input, fan off or inadequate separation. Summarize eligible coverage and out-of-range fractions by equipment without labelling them automatically as faults.

## Experiment

Hold return temperature at 24 °C and mixed air at 23.9 °C. Compare outdoor temperatures of 12, 23.8 and 24 °C in scratch data. Predict the sensitivity and undefined case before running. Then perturb mixed air by 0.2 °C.

## Acceptance checks

- The tiny example produces fraction 0.5, with percentage conversion applied exactly once.
- Equal temperatures never cause division by zero.
- The declared separation threshold appears in report metadata.
- No report substitutes `damper_pct / 100` for the computed fraction or claims the simplified calculation proves an economizer fault.

## Stretch and reflection

What happens if one temperature is Fahrenheit while the others are Celsius? Explain why unit validation belongs before the formula rather than after aggregation.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day37/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-6) for exact language and domain details.

[Previous: Day 36](day36.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 38](day38.md)
