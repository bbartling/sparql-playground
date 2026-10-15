# Day 47 — Separate rule applicability from per-equipment tuning

[Previous: Day 46](day46.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 48](day48.md)

**Week 7 · 45–75 minutes.** Prerequisites: Days 1–46, or equivalent SQL skills.

## Goal

Check whether a rule has suitable inputs before applying an equipment-specific threshold policy.

## Before you start

Use equipment UUIDs from `course.equipment`, not labels. All starter AHUs have the teaching pressure roles, but future equipment or a changed graph may not. Do not assume that successful evaluation on one AHU proves fleet applicability.

## Concept

Applicability asks whether equipment kind, roles, units and selection policy support a rule. Tuning chooses thresholds, delays and confirmation settings for applicable equipment. Missing roles are an applicability result; missing samples during an otherwise applicable window are data availability. Keep those reasons distinct.

Represent tuning as data keyed by equipment identity and rule version, with units, effective bounds and provenance. A threshold from one AHU should not leak to another equipment that shares its label. Conflicting effective policy rows can multiply evaluations just like a faulty sensor join. Validate one selected policy per equipment and instant; do not quietly take the first row.

## Tiny example

```sql
SELECT equipment_id, role, count(*) AS matching_points
FROM course.point
WHERE role IN ('duct_static', 'duct_static_sp', 'fan_status')
GROUP BY equipment_id, role
HAVING count(*) <> 1;
```

The starter fixture returns no rows. This detects duplicates among present roles, but cannot detect an entirely absent role without an expected-role relation.

## SQL challenge

Create scratch rule-requirement and equipment-policy relations. Audit each AHU for required roles, compatible units and exactly one selected point. Give policies a pressure ratio, warmup seconds and confirmation count with validated ranges. Demonstrate both a missing role and duplicate policy using scratch metadata.

## Experiment

Give north and south Supply A different scratch ratios while retaining the same labels. Confirm each receives only its own policy. Then create overlapping effective rows for one equipment and make your audit reject ambiguity before evaluation.

## Acceptance checks

- Starter pressure applicability succeeds for three distinct equipment UUIDs.
- Missing role, ambiguous role selection, incompatible unit and missing sample have different explanations.
- Overlapping policies cannot silently double fault seconds.
- A tuning change records a policy identity and is described as a changed rule configuration.

## Stretch and reflection

Would a ratio threshold transfer better than an absolute Pa threshold? Explain what equipment knowledge would still be required before choosing either one.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day47/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-7) for exact language and domain details.

[Previous: Day 46](day46.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 48](day48.md)
