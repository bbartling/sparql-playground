# Day 78 — Trace the production SQL input boundary

[Previous: Day 77](day77.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 79](day79.md)

**Week 12 · 45–75 minutes.** Prerequisites: Days 1–77, or equivalent SQL skills.

## Goal

Read Open-FDD’s schemas and execution adapter and distinguish source templates from the SQL actually executed.

## Before you start

Open the pinned 3.6.15 references in [Open-FDD bridge](OPENFDD_BRIDGE.md). Treat the production repository as read-only. The course’s Brick profile and Open-FDD’s Haystack model have separate identities and role vocabularies; use an explicit adapter.

## Concept

The production long sample key is site, `openfdd_key` and timestamp. Its SQL input adapter builds a per-run temporary `history` relation with equipment ID, timestamp and role columns. The helper schema marker does not create that wide history itself. Trace `ensure_history_table`, `fill_history_for_equipment`, rendering and execution in `timescale_product.rs`. Compare with registry metadata and PostgreSQL helper functions. Numeric `{{...}}` rendering belongs to trusted reviewed templates with validated tuners; bound `$1` values belong to the execution interface. They serve different purposes and require separate validation.

## Tiny example

```sql
SELECT site_id, equipment_id,
       ts AS timestamp_utc,
       fan_speed_pct / 100.0 AS fan_cmd,
       fan_status
FROM course.ahu_5m
WHERE site_id = 'SYN-NORTH'
  AND ts >= '2026-01-05 08:00Z'::timestamptz
  AND ts < '2026-01-05 08:15Z'::timestamptz
ORDER BY equipment_id, timestamp_utc;
```

The explicit percent-to-fraction conversion is safe because the course unit is declared. Renaming a pressure column does not convert Pa into a catalog tuner’s in.w.c.

## SQL challenge

Create a mapping document for all fourteen course roles: source unit, target role/unit, conversion, null/quality behavior and applicability. Build a scoped scratch view for FC1’s required and optional inputs. Resolve UUIDs through metadata; define how duplicate same-role sensors would be rejected or selected. Identify the minimum helper dependencies from the pinned SQL rather than installing an entire production schema.

## Experiment

Trace one catalog rule from its registry path through the actual PostgreSQL path selection, template rendering, temporary-history population and query wrapper. Record where site, equipment, window, equipment kind and missing roles are enforced. Mark a boundary as unverified when the source evidence is incomplete.

## Acceptance checks

- The trace identifies SQL input grain and actual execution engine.
- Roles and units have explicit conversions; unknown mappings remain unsupported.
- The fixture adapter keeps bad/missing input null.
- No production SQL is executed against application data.

## Stretch and reflection

Why can a permanent wide helper name in a comment mislead a reader about runtime behavior?

Save your SQL, actual output, and one explanation in `student-work/sql/day78/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-12).

[Previous: Day 77](day77.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 79](day79.md)
