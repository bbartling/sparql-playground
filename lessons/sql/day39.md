# Day 39 — Weight aggregates and define a scatter dataset

[Previous: Day 38](day38.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 40](day40.md)

**Week 6 · 45–75 minutes.** Prerequisites: Days 1–38, or equivalent SQL skills.

## Goal

Produce numerically defensible summaries and a precise row contract for a future scatter plot.

## Before you start

Reuse your interval and eligibility policies. A plot is optional; the required artifact is an auditable SQL result that could support one. Today uses plain PostgreSQL, with no plotting service or Timescale feature.

## Concept

For a temperature or power mean over time, use `sum(value × valid_seconds) / sum(valid_seconds)`. A mean of means is valid only when the underlying weights are appropriate. Two AHUs with different runtime or coverage should not receive equal time weight accidentally. Conversely, a fleet metric intended to give each equipment equal influence needs that distinct policy named.

A scatter result needs a row grain before it needs colors. Define one row per site/equipment/time interval, an OAT x-axis in °C, power y-axis in kW, matched timestamps, interval weight and eligibility fields. Joining independent point histories on timestamp alone can cross equipment boundaries. A point cloud can reveal associations; it does not by itself establish causation or diagnose a fault.

## Tiny example

```sql
SELECT sum(kw * seconds) / sum(seconds) AS time_weighted_kw
FROM (VALUES (12.0, 300), (6.0, 60)) AS v(kw, seconds);
```

The weighted result is 11 kW; the unweighted mean is 9 kW.

## SQL challenge

Create a scratch view for fan-on OAT-versus-power scatter rows over a bounded window. Include site, equipment UUID, timestamp, OAT, kW, valid seconds and a source label. Produce both per-equipment time-weighted means and a fleet time-weighted mean from the underlying weighted sums.

## Experiment

Compare a fleet result assembled from sums and weights with an average of equipment averages. Make an unequal-weight scratch example if the fixture happens to obscure the difference. Predict which equipment dominates the time-weighted result and why.

## Acceptance checks

- The tiny example returns 11 kW.
- Scatter rows have a unique declared key and no cross-site label collisions.
- Missing power never appears as a known 0 kW point.
- Weighted sums and weights reproduce the final mean; plotted row count alone is not presented as valid duration.

## Stretch and reflection

What would equal-equipment weighting answer that time weighting would not? Name both metrics as a dashboard reader should see them.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day39/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-6) for exact language and domain details.

[Previous: Day 38](day38.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 40](day40.md)
