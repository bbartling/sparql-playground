# Day 74 — Freeze model revisions and copy runs consistently

[Previous: Day 73](day73.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 75](day75.md)

**Week 11 · 45–75 minutes.** Prerequisites: Days 1–73, or equivalent SQL skills.

## Goal

Define a reproducible run that cannot mix two model revisions or silently reuse stale cached results.

## Before you start

Use invented revision identifiers and scratch tables. Keep RDF and SQL fixtures as references. No production model, cache or run is changed.

## Concept

A model revision determines point-role bindings and equipment membership. A result run also depends on data window, query version, tuners and data revision. A database snapshot can keep SQL reads consistent; it cannot automatically freeze an RDF graph held by another service. Resolve a single immutable model revision, record its identity and use an explicit SQL isolation policy. Copying a run should copy its complete child cohort atomically, not just its header. Cache keys and invalidation must account for these identities.

## Tiny example

```sql
CREATE TABLE student.run_demo (
  run_id integer PRIMARY KEY, model_rev text NOT NULL,
  query_rev text NOT NULL
);
CREATE TABLE student.result_demo (
  run_id integer REFERENCES student.run_demo,
  equipment_id uuid NOT NULL, metric text NOT NULL,
  bucket timestamptz NOT NULL, value double precision,
  PRIMARY KEY (run_id, equipment_id, metric, bucket)
);
```

The foreign key prevents orphan results. It does not prove the whole intended equipment cohort was copied.

## SQL challenge

Create a run containing one explicitly scoped fixture equipment cohort and its hourly metric. Design an atomic copy to a new run ID using an explicit column list. Preserve original model/query revisions and record copy provenance separately. Add assertions for child counts, equipment identities and hourly bucket keys. Demonstrate that a failure midway through the copy rolls back the new header and children together.

## Experiment

In another session, change a scratch point-role selection while a reader performs two queries. Compare read-committed with a repeatable-read transaction. Then explain which external RDF state still requires a separately frozen revision. Invalidate one cached answer by changing its model or query revision.

## Acceptance checks

- Every result has exactly one parent run and declared revision identities.
- The copied cohort equals the source cohort, with no duplicate or missing children.
- Failed copying leaves no partial destination run.
- The report states the SQL snapshot and external-model consistency boundary.

## Stretch and reflection

Should copying a run refresh its source data? State an explicit semantic choice and its consequences for provenance.

Save your SQL, actual output, and one explanation in `student-work/sql/day74/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-11).

[Previous: Day 73](day73.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 75](day75.md)
