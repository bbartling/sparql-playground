# Day 18 — Compare neighboring observations with LAG and LEAD

[Previous: Day 17](day17.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 19](day19.md)

**Week 3 · 45–75 minutes.** Prerequisites: days 1–17, or equivalent skills.

## Goal

Use the previous or next observation to detect unusual spacing while preserving the identity and time ordering of each sensor history.

## Before you start

Set your session timezone to UTC. Review window partitions. The fixture uses five-minute cadence, but two pressure observations are absent on Jan 5. A stored row with a null value remains a row; it does not create a timestamp gap by itself.

## Concept

`lag(ts)` returns the previous row's timestamp within the ordered partition; `lead(ts)` returns the next. The first or last row has no neighbor in that direction, so the function returns null by default. That boundary null is different from a missing measurement.

Timestamp subtraction produces an interval. A gap detector compares that interval with an expected cadence. It detects an interruption between observed rows but does not establish the values during the interruption. The neighbor population matters: filtering to good rows before `lag` measures gaps between usable observations; retaining every stored row measures storage cadence.

## Tiny example

```sql
WITH neighbors AS (
    SELECT site_id, point_id, ts,
           lag(ts) OVER (
               PARTITION BY site_id, point_id ORDER BY ts
           ) AS previous_ts
    FROM course.history
    WHERE role = 'duct_static'
)
SELECT site_id, point_id, previous_ts, ts,
       ts - previous_ts AS observed_gap
FROM neighbors
WHERE ts - previous_ts > INTERVAL '5 minutes'
ORDER BY site_id, point_id, ts;
```

Exactly one row has a gap of fifteen minutes: the affected pressure point jumps from 08:20 to 08:35 UTC on Jan 5. This implies two expected interior instants are absent, not fifteen minutes of known pressure behavior.

## SQL challenge

Create a bounded neighbor report for `kw` observations. Include current quality and value along with previous and next timestamps. Verify that the stored power rows retain normal cadence around the bad/null observation at 15:10 UTC on Jan 5. Then compare with a version whose window input contains only usable power observations. Explain the different question each report answers.

Use point identities in partitions and retrieve equipment metadata only through the established relationship. Describe the expected behavior at the first and last fixture observations.

## Experiment

Restrict the pressure CTE's input to an 08:30–09:00 window and rerun the detector. Its first visible row no longer sees 08:20. Compare that with calculating neighbors first and applying the report window afterward. Explain why a query can miss a boundary gap without any SQL error.

## Acceptance checks

- The pressure detector reports one 15-minute observed gap at the expected instants.
- Your power report distinguishes storage cadence from usable-value cadence.
- Your notes account for window boundaries and neighbor nulls.

## Stretch and reflection

What additional expected timestamp series would reveal missing observations before the first stored row or after the last? Outline the needed information without assuming `lag` can create absent rows. Read [week 3 references](SOURCES.md#week-3) for offset window functions.

[Previous: Day 17](day17.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 19](day19.md)
