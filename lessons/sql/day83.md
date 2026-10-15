# Day 83 — Review a migration and an execution test plan

[Previous: Day 82](day82.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 84](day84.md)

**Week 12 · 45–75 minutes.** Prerequisites: Days 1–82, or equivalent SQL skills.

## Goal

Prepare a concrete review packet for moving one model-driven diagnostic and one analytics query toward deployment.

## Before you start

Use the preceding lessons’ SQL, tests, manifests and contracts. Keep production read-only. This is a review and proposal exercise; deployment approval is outside the lab.

## Concept

A migration changes installed behavior and data assumptions. A review packet should make identity, grain, units, scope, parameter validation, applicability, cancellation, result typing and provenance inspectable. Source parity does not prove installed parity; equal totals do not prove equal timestamp masks. A controlled rollout needs success criteria, observability and a recovery plan compatible with any data changes. Record unanswered questions as specific tests, not generic assurance.

## Tiny example

```sql
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'student'
  AND table_name IN ('rule_inventory', 'run_demo', 'result_demo')
ORDER BY table_name, ordinal_position;
```

Compare these actual objects with the manifest your proposal expects. An absent object is evidence of an incomplete local installation, even when its migration file exists.

## SQL challenge

Write a migration proposal for your scoped SQL input adapter, versioned rule/analytics contracts and run/result storage. Include explicit columns, logical/composite keys, indexing, installed-schema checks and least-privilege assumptions. Supply a test plan covering fresh install, applicable upgrade, wrong-site queries, duplicate same-role sensors, unit conversions, null/gap input, cancellation cleanup, full FC1 masks and the day81 channel counterexample. Identify required checks before any rollout.

## Experiment

Review a deliberately flawed scratch change: remove a site component from a join, broaden a missing-equipment query, or copy only a run header. Use existing tests to expose the problem. Produce a concise code-review comment with the concrete trigger, wrong result and required behavior.

## Acceptance checks

- The packet contains reviewable SQL/DDL and a test matrix with expected outcomes.
- Source, rendered SQL, installed schema and result provenance have distinct checks.
- Each unrun deployment requirement has an owner or explicit environment need.
- Performance evidence includes bounded scope and failure behavior.
- Recovery handles partial failures without presenting incomplete runs as complete.

## Stretch and reflection

What evidence would justify promotion from a synthetic lab to a monitored pilot? Which requirements still need domain review?

Save your SQL, actual output, and one explanation in `student-work/sql/day83/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-12).

[Previous: Day 82](day82.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 84](day84.md)
