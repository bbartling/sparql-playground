# Day 79 — Inventory all 77 rules and the separate analytics pack

[Previous: Day 78](day78.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 80](day80.md)

**Week 12 · 45–75 minutes.** Prerequisites: Days 1–78, or equivalent SQL skills.

## Goal

Make applicability and output type inspectable for the complete pinned FDD catalog.

## Before you start

Use the pinned registry and the complete inventory in [Open-FDD bridge](OPENFDD_BRIDGE.md). Inventory all 77 rule entries; a few familiar AHU rules are insufficient. Read the separate analytics registry without counting its query bodies as additional FDD rules.

## Concept

A catalog carries rule IDs and aliases, equipment kinds, required/optional roles, output columns, tuners, units and defaults. These fields are an execution contract. Missing required roles differ from optional columns filled with null, and metadata existence differs from usable sample coverage. Some entries produce metrics rather than fault hours. Current runtime classification uses output columns; inspect it rather than assuming every catalog entry is a diagnostic. Catalog inclusion, dashboard wiring and successful qualification are separate claims.

## Tiny example

```sql
WITH catalog(rule_id, output_columns) AS (
  VALUES ('FC1', ARRAY['equipment_id', 'fault_hours']),
         ('FAN-RUNTIME-HOURS',
          ARRAY['equipment_id', 'fan_runtime_hours', 'total_hours'])
)
SELECT rule_id,
  output_columns && ARRAY['fault_hours', 'fault_pct', 'fault_samples']
    AS diagnostic_shape
FROM catalog ORDER BY rule_id;
```

This reproduces a classification concept for two entries; it does not assert that those entries have passed execution tests.

## SQL challenge

Import or transcribe the full pinned catalog into `student.rule_inventory`. Preserve aliases, SQL path, equipment kinds, required/optional roles, output columns, tuner names/types/ranges/units/defaults and the revision. Use a normalized tuner child table or structured JSON with validation. Produce counts by output shape and equipment kind, plus an applicability report for the course AHUs. Mark unsupported roles explicitly instead of manufacturing source data.

## Experiment

Remove one required-role mapping for one scratch equipment item and contrast it with removal of an optional mapping. Record expected skip, null-column or ineligible behavior from the actual adapter. Inspect a non-AHU rule and explain why this course fixture cannot qualify it.

## Acceptance checks

- There are exactly 77 distinct canonical rule IDs and no duplicate alias ownership.
- Inventory includes metric entries and every tuner’s declared metadata.
- Applicability retains site/equipment scope and explicit missing roles.
- The 18 analytics query bodies have their own inventory and statuses.

## Stretch and reflection

Which checks would detect a new registry entry whose executable SQL file was omitted from packaging?

Save your SQL, actual output, and one explanation in `student-work/sql/day79/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-12).

[Previous: Day 78](day78.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 80](day80.md)
