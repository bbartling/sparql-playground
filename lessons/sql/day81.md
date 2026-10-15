# Day 81 — Separate a SQL metric from a runtime analytics query

[Previous: Day 80](day80.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 82](day82.md)

**Week 12 · 45–75 minutes.** Prerequisites: Days 1–80, or equivalent SQL skills.

## Goal

Implement one metric with a known answer and review a similarly named production query for different semantics.

## Before you start

Read pinned `fan_runtime_hours.sql`, the analytics `motor_weekly_runtime.sql`, and their actual callers through [Open-FDD bridge](OPENFDD_BRIDGE.md). Use only course or handcrafted scratch input.

## Concept

The catalog metric `FAN-RUNTIME-HOURS` uses non-null normalized `fan_cmd > 0.05`, then multiplies row counts by polling seconds. Its `total_hours` is eligible command-row duration, not a guaranteed complete window. The separate runtime analytics query counts matching status and command sample rows, uses a fixed 300 seconds and binds site only. Both channels can count the same instant twice; `LIMIT 500` bounds returned groups without bounding historical scan work. Similar names do not establish equivalent equations. Review the source behavior before selecting a contract.

## Tiny example

```sql
WITH input(channel, val) AS (
  VALUES ('fan_status', 1.0), ('fan_cmd', 0.7)
)
SELECT count(*) FILTER (WHERE val > 0.05) * 300.0 / 3600.0
       AS row_count_hours
FROM input;
```

Two active channels yield one sixth of an hour from a single five-minute instant. A one-signal runtime definition would yield one twelfth. This is a counterexample to using multi-channel row counts as the oracle.

## SQL challenge

Execute the full catalog metric in a scoped scratch environment after converting course `fan_speed_pct` to a fraction. For north Supply A on January 5, expect 12 command-on hours and 24 eligible timeline hours. Build a bounded analytics query over the same equipment/window with one explicitly selected authoritative signal. Include coverage and compare its result with the catalog metric. Any deliberate equation correction must have its own version and tests.

## Experiment

Add status and command for the same instants to a handcrafted long table, then remove one channel. Contrast the production analytics equation with your chosen single-signal contract. Introduce a gap and explain the polling assumption separately from duplicate-channel effects.

## Acceptance checks

- Both source query paths and their bind parameters are identified.
- A hand-derived counterexample detects double counting.
- Your query has site, identity and finite time bounds.
- Results declare units, denominator, authoritative signal and equation version.

## Stretch and reflection

Which metric requires interval integration rather than multiplying sample counts by a nominal cadence?

Save your SQL, actual output, and one explanation in `student-work/sql/day81/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-12).

[Previous: Day 80](day80.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 82](day82.md)
