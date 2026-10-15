# Day 20 — Build explicit conditional summaries and pivots

[Previous: Day 19](day19.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 21](day21.md)

**Week 3 · 45–75 minutes.** Prerequisites: days 1–19, or equivalent skills.

## Goal

Use aggregate `FILTER` clauses to summarize quality and place selected roles beside each other, while proving the input grain supports the pivot.

## Before you start

Review grouped aggregates and role/unit metadata. A long table has one row per point and instant; a pivot can have one row per equipment and instant with separate columns for different roles. Each numeric output still needs its own unit.

## Concept

`count(*) FILTER (WHERE ...)` counts only the rows matching that aggregate's condition. Other aggregates in the same group can use different filters. This preserves a visible distinction between stored rows, usable rows, and bad/null rows.

A conditional pivot often uses `max(value) FILTER (WHERE role = ...)` to extract a role's value. Here `max` is safe only after establishing at most one selected point per equipment and role at each instant. It must not silently choose the highest of duplicate same-role sensors. Missing source rows and excluded bad values both produce null pivot cells, so retain a quality report to explain them.

## Tiny example

```sql
SELECT site_id, equipment_id, ts,
       max(value) FILTER (
           WHERE role = 'duct_static'
             AND quality = 'good' AND value IS NOT NULL
       ) AS duct_static_pa,
       max(value) FILTER (
           WHERE role = 'duct_static_sp'
             AND quality = 'good' AND value IS NOT NULL
       ) AS duct_static_sp_pa
FROM course.history
WHERE site_id = 'SYN-NORTH'
  AND ts = TIMESTAMPTZ '2026-01-05 08:25:00+00'
GROUP BY site_id, equipment_id, ts
ORDER BY equipment_id;
```

The result has two equipment rows. One pressure cell is null because that observation is absent; its setpoint is still 250 Pa. The other AHU has its own values.

## SQL challenge

Build a daily UTC quality report per site and role, with stored count, usable count, and bad/null count using explicit filters. Identify the single unusable `kw` sample without turning it into a zero.

Build a bounded instantaneous pivot for `fan_status`, `fan_speed_pct`, and `kw` with descriptive aliases. Show each role's unit in your report notes. Compare with the same rows from `course.ahu_5m`, which provides all fourteen teaching roles. This view does not resample time or fill absent values.

## Experiment

Inspect the Jan 5 15:10 UTC power pivot. One equipment's power cell is null even though its fan-status observation is present. Explain why an aggregate across available values cannot establish the missing power value. Then count `course.ahu_5m`: it has 1,728 equipment/instant rows despite the two missing pressure samples.

## Acceptance checks

- Your pivot retains equipment identity and has one row per equipment/instant.
- Your quality report accounts for the one bad/null power observation.
- You establish the starter fixture's single-point-per-role assumption before using `max` as extraction.

## Stretch and reflection

Compare a conditional aggregate with `CASE` inside an aggregate. Which makes your quality rule easier to review? Read [week 3 references](SOURCES.md#week-3) for aggregate filters and conditional expressions.

[Previous: Day 19](day19.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 21](day21.md)
