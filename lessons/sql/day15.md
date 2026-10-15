# Day 15 — Query UTC instants with half-open windows

[Previous: Day 14](day14.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 16](day16.md)

**Week 3 · 45–75 minutes.** Prerequisites: days 1–14, or equivalent skills.

## Goal

Select exact time windows, distinguish an instant from its display timezone, and explain why adjacent windows should share a boundary without sharing observations.

## Before you start

Connect to the course database. Run `SHOW timezone;` and record the result. The fixture begins at `2026-01-05T00:00:00Z` and stops before `2026-01-07T00:00:00Z`. Each complete point has 576 observations at five-minute cadence.

## Concept

A `timestamptz` stores an instant. PostgreSQL displays it using the session timezone; changing that setting does not move the stored observation. A timestamp literal with an explicit `+00` offset makes the intended UTC instant clear. A local timestamp without an offset needs a timezone interpretation, and daylight-saving changes can make local clock labels ambiguous or nonexistent.

Use a half-open window: `ts >= start AND ts < end`. An observation exactly at the end belongs to the next window. This lets adjacent reports partition time cleanly. `BETWEEN` includes both endpoints, which can double count a boundary when used for adjacent windows.

## Tiny example

```sql
SET TIME ZONE 'UTC';
SELECT count(*) AS stored_pressure_rows
FROM course.history
WHERE role = 'duct_static'
  AND ts >= TIMESTAMPTZ '2026-01-05 08:00:00+00'
  AND ts <  TIMESTAMPTZ '2026-01-05 09:00:00+00';
```

Expect 34 rows: three pressure points would normally contribute 36, but two observations are absent. This is a count of stored rows, not a duration calculation.

## SQL challenge

Build two adjacent one-hour reports for pressure observations, grouped by site and point identity. Include the start and end instants in your report notes. Identify which first-window point has 10 rows rather than the usual 12, then retrieve its equipment metadata through identities.

Verify that the sum of both adjacent-window counts equals the count for their combined two-hour window. State whether the boundary observation appears in the earlier or later report. Keep quality counts separate from missing-row counts.

## Experiment

Display one known timestamp with `SET TIME ZONE 'UTC'`, then with `SET TIME ZONE 'America/Chicago'`. The UTC midnight fixture instant displays as the preceding evening in Chicago. Confirm its identity and numeric value stay the same, then restore UTC. Compare a `BETWEEN` one-hour count with the half-open count: the inclusive endpoint adds one observation per pressure point at 09:00.

## Acceptance checks

- The 08:00–09:00 UTC pressure count is 34, and your affected point has 10 rows.
- Adjacent half-open windows reconcile with their combined window.
- Your notes distinguish UTC instants, local display, and inclusive/exclusive boundaries.

## Stretch and reflection

Convert an instant with `AT TIME ZONE` and inspect the resulting type using `pg_typeof`. Why does a local calendar day require timezone-aware boundary construction? Read [week 3 references](SOURCES.md#week-3) before assuming every local day is 24 hours.

[Previous: Day 14](day14.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 16](day16.md)
