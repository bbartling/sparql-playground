# Day 75 — Check installed schema against a versioned manifest

[Previous: Day 74](day74.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 76](day76.md)

**Week 11 · 45–75 minutes.** Prerequisites: Days 1–74, or equivalent SQL skills.

## Goal

Detect when installed database objects differ from the schema a query and its tests expect.

## Before you start

Use catalog reads and scratch migrations. Keep your source manifest small and versioned with coursework. The lab ownership sentinel identifies the dedicated database; it is not an authorization mechanism.

## Concept

A migration file states intended changes; installed catalogs state what actually exists. A version number alone cannot prove columns, constraints, policies and views match. A contract manifest can list object names, columns/types/nullability, keys, relevant constraints, view definitions and expected extension versions. Compare a canonical representation rather than unstable OIDs or generated names. CI should install from a clean database and test the resulting schema, then exercise an upgrade path where relevant.

## Tiny example

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'course' AND table_name = 'sample'
ORDER BY ordinal_position;

SELECT schema_version, purpose
FROM course.lab_meta WHERE singleton;
```

These answer different questions: actual column properties and the declared lab schema version.

## SQL challenge

Create a manifest for `course.sample`, its ownership relationships and the eligibility contract. Include the composite logical key and finite-value/quality checks. Write a catalog-based check that fails when a scratch copy loses one expected constraint or changes a column’s nullability. Distinguish a PostgreSQL type’s internal name from the display form returned by `information_schema`.

## Experiment

Apply a harmless scratch migration, update its expected manifest, and then simulate drift by changing only the installed schema. Confirm that the check catches the discrepancy even if a version table still claims success. Restore the scratch schema before recording the passing run.

## Acceptance checks

- A clean installed schema matches the declared manifest.
- At least one missing-constraint mutation fails.
- Check output identifies the mismatched property clearly.
- Proposed CI runs SQL assertions with failure propagation and records server/extension versions.
- Migration review includes both fresh install and applicable upgrade behavior.

## Stretch and reflection

Which server-generated details should be excluded from a portable manifest? Which database features demand explicit version gating?

Save your SQL, actual output, and one explanation in `student-work/sql/day75/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-11).

[Previous: Day 74](day74.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 76](day76.md)
