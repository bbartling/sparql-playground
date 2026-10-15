# Day 80 — Audit and exercise the complete FC1 diagnostic

[Previous: Day 79](day79.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 81](day81.md)

**Week 12 · 45–75 minutes.** Prerequisites: Days 1–79, or equivalent SQL skills.

## Goal

Explain FC1’s full pinned algorithm and verify its confirmation behavior using adapted synthetic input.

## Before you start

Read FC1’s PostgreSQL template, registry parameters and parameter derivation through [Open-FDD bridge](OPENFDD_BRIDGE.md). Use a session-local temporary `history` populated only from scoped fixture data. Record conversions so pressure inputs and `EPS_DSP` share units.

## Concept

FC1 includes operational gating, fan-status precedence, a full-fan gate, startup/mode delay, low-pressure comparison, raw-fault streaks, confirmation and a minimum-active-coverage rule. Its implementation counts confirmed rows times declared polling seconds. A row streak is not automatically elapsed-time continuity. Raising confirmation excludes early streak rows; the template does not retroactively credit the whole streak. Review null/fallback branches as authored. These are production-study semantics, not an endorsement that row counts suit irregular data.

## Tiny example

```sql
WITH streak(raw_fault, streak_len) AS (
  VALUES (1, 1), (1, 2), (1, 3), (0, 1)
)
SELECT raw_fault, streak_len,
       CASE WHEN raw_fault = 1 AND streak_len >= 3
            THEN 1 ELSE 0 END AS confirmed
FROM streak ORDER BY raw_fault DESC, streak_len;
```

Only the third fault row is confirmed. This example isolates one mechanism; it is not FC1’s complete predicate.

## SQL challenge

Render and run the full pinned PostgreSQL FC1 template against north Supply A on January 5. Freeze all effective tuners and adapt role names/units explicitly. Keep the regular 288-row equipment timeline, including null pressure at the two missing instants. With default 300-second confirmation, expect ten confirmed five-minute rows: 50 observed fault minutes. With 900-second confirmation, two five-row raw streaks yield six confirmed rows: 30 minutes. Verify timestamp masks as well as totals. For mask evidence, use an audit copy that carries `timestamp_utc` through `final` and selects it with `confirmed`; retain the unchanged template for aggregate parity.

## Experiment

In scratch input, set status off while command stays on, then make status null. Explain the changed precedence. Separately delete intervening timeline rows and demonstrate why adjacent-row confirmation needs a cadence/gap contract. Document differences from the course’s bounded-duration predicate.

## Acceptance checks

- Every FC1 gate and effective tuner is accounted for.
- Full-template outputs match independently hand-counted masks.
- Pressure units and percent/fraction handling are explicit.
- Missing roles, null input and insufficient coverage have declared statuses.

## Stretch and reflection

How would you distinguish authored row-count parity from a proposed elapsed-time correction?

Save your SQL, actual output, and one explanation in `student-work/sql/day80/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-12).

[Previous: Day 79](day79.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 81](day81.md)
