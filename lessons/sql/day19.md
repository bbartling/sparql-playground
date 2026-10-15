# Day 19 — Bound valid coverage instead of bridging gaps

[Previous: Day 18](day18.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 20](day20.md)

**Week 3 · 45–75 minutes.** Prerequisites: days 1–18, or equivalent skills.

## Goal

Translate a declared sample-support convention into bounded coverage, and report unknown time separately. Counts become durations only after you choose a support rule.

## Before you start

Read the fixture's convention in [the contract](CONTRACT.md): a usable sample can represent at most 300 seconds, clipped to the requested half-open window. A long gap cannot extend the preceding value indefinitely. Today studies coverage, not proof of a process state between measurements.

## Concept

Treat a usable observation at `ts` as supporting a forward interval that ends at the earliest of the next observation, `ts + 5 minutes`, and the report end. Clip the start to the report start. A positive interval contributes coverage; a bad/null row contributes none. A report beginning between samples may need the immediately preceding observation to assess the opening interval.

This is a teaching convention. It does not demonstrate that the physical value stayed constant. Scheduled fan hours, hours inferred from observed fan status, pressure coverage, and unknown intervals are distinct quantities. Never substitute one for another without declaring why it answers the question.

## Tiny example

```sql
WITH pressure_neighbors AS (
    SELECT site_id, point_id, ts, value, quality,
           lead(ts) OVER (
               PARTITION BY site_id, point_id ORDER BY ts
           ) AS next_ts
    FROM course.history
    WHERE role = 'duct_static'
)
SELECT site_id, point_id, ts, next_ts,
       least(ts + INTERVAL '5 minutes',
             coalesce(next_ts, ts + INTERVAL '5 minutes'),
             TIMESTAMPTZ '2026-01-05 09:00:00+00') - ts
           AS supported_interval
FROM pressure_neighbors
WHERE site_id = 'SYN-NORTH'
  AND ts = TIMESTAMPTZ '2026-01-05 08:20:00+00'
  AND quality = 'good' AND value IS NOT NULL
ORDER BY point_id;
```

Both northern pressure rows support five minutes. One next observation is fifteen minutes away; its support still ends at 08:25.

## SQL challenge

Report usable pressure coverage per point for the exact 08:00–09:00 UTC window. State the grain, quality rule, support convention, and seconds unit before writing the formula. Report requested seconds, covered seconds, and unknown seconds together. Ensure support cannot extend outside the window or become negative.

The affected point should cover 3,000 of 3,600 seconds, leaving 600 unknown. Each other pressure point covers all 3,600 seconds. Explain why the fifteen-minute neighbor gap does not mean fifteen minutes are all unknown under this convention.

## Experiment

Change the report start to 08:22. Include the preceding 08:20 observation when constructing support, then clip it to the new start. Compare with filtering all input rows to `ts >= start`. The latter loses legitimate opening support. Record this boundary limitation explicitly.

## Acceptance checks

- Your one-hour report produces the stated 3,000/600 and 3,600/0 coverage pairs.
- No usable row represents more than 300 seconds.
- Bad/null values and unsupported gaps never become known coverage.

## Stretch and reflection

How would irregular sampling change the support policy? Describe a requirement and a test before choosing interpolation. Read [week 3 references](SOURCES.md#week-3) for date arithmetic and window functions.

[Previous: Day 18](day18.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 20](day20.md)
