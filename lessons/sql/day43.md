# Day 43 — Express a fault predicate without turning unknown into healthy

[Previous: Day 42](day42.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 44](day44.md)

**Week 7 · 45–75 minutes.** Prerequisites: Days 1–42, or equivalent SQL skills.

## Goal

Translate a small pressure rule into SQL while preserving off, unavailable, pass and candidate states.

## Before you start

Use `course.ahu_5m`; it aligns roles by equipment and instant without filling missing inputs. Review the full Open-FDD distinction in [the bridge notes](OPENFDD_BRIDGE.md). Today's SQL is a teaching predicate, not the complete production FC1 algorithm.

## Concept

Our candidate condition is `duct_static < 0.9 * duct_static_sp` while valid `fan_status = 1`. Pressure and setpoint are Pa. Require eligible inputs, binary status and positive setpoint. Fan off is excluded from evaluation. Missing inputs while the fan is on produce unknown, not a pass. Good data that fails the candidate condition produces evaluated false.

SQL has true, false and null/unknown. `WHERE predicate` retains only true rows, discarding false and unknown alike. `COALESCE(predicate, false)` can erase a data-quality problem. Preserve an evaluation-state column before filtering candidates. The alternative threshold `static < setpoint - 50 Pa` happens to classify this fixture identically, but is a different rule for other setpoints.

## Tiny example

```sql
SELECT measured_pa,
       measured_pa < 0.9 * 250.0 AS raw_candidate
FROM (VALUES (100.0), (225.0), (260.0), (NULL)) AS v(measured_pa);
```

Results are true, false, false and null. Equality at the threshold does not satisfy a strict `<` comparison.

## SQL challenge

Produce a bounded evaluation detail table for every equipment and timestamp. Include pressure, setpoint, fan state, input validity, evaluation state and nullable candidate Boolean. Summarize evaluated-true, evaluated-false, off and unknown time separately using the interval policy.

## Experiment

Compare `WHERE raw_candidate`, `WHERE NOT raw_candidate` and `WHERE raw_candidate IS NULL` on your scratch values. Add fan-off rows with missing pressure and document your state precedence before querying.

## Acceptance checks

- North Supply A has ten raw candidate samples on Jan 5, with two unknown pressure instants inside the planted excursion.
- The other equipment have no raw pressure candidates.
- Off rows are labelled excluded; missing on-state pressure never becomes a healthy pass.
- A 225 Pa measurement at a 250 Pa setpoint is false under the strict teaching predicate.

## Stretch and reflection

What evidence does a candidate provide about cause? Explain why a low-pressure condition alone cannot prove a failed fan or a sensor fault.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day43/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-7) for exact language and domain details.

[Previous: Day 42](day42.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 44](day44.md)
