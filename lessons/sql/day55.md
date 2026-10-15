# Day 55 — Review graph changes and inspect the read-only web boundary

[Previous: Day 54](day54.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 56](day56.md)

**Week 8 · 45–75 minutes.** Prerequisites: Days 1–54, or equivalent SQL skills.

## Goal

Understand graph CRUD and revision consistency while using only the implemented read surface.

## Before you start

The offline course helper supports SELECT/ASK and reference resolution. The existing brickts HTTP API has its own building model and SQLite history; it is separate from the PostgreSQL course fixture. HTTP examples below are learner-run only when that local app is already prepared according to the repository guide.

## Concept

CRUD means create, read, update and delete. For graph metadata, an update can change a point's owner, unit or external reference while its history remains stored elsewhere. A staged model change should validate reference cardinality, identity and store reachability before publication. A reader should resolve against one coherent model revision; caching a point mapping across a model replacement can read the wrong history.

These are design requirements, not promises that this course exposes mutation endpoints or revision tokens. The shipped SPARQL boundary is read-only. Record a captured model file and its checksum as evidence of the exact artifact you examined. A Turtle byte checksum identifies those bytes, not semantic equivalence across differently ordered serializations.

## Tiny example

```bash
curl --fail http://127.0.0.1:8000/api/model/ttl?scope=model
curl --fail -X POST http://127.0.0.1:8000/api/sparql \
  -H 'Content-Type: application/json' \
  --data '{"query":"ASK { ?s ?p ?o }"}'
```

These inspect the app's graph. The SPARQL response wraps typed results in `results` plus `meta`; offline helper JSON is the direct SPARQL result. `GET /api/points/{point_id}/timeseries` accepts app-discovered point IDs, optional integer epoch-second `start`/`end`, and `limit`. Do not substitute course UUIDs into a different model.

## SQL challenge

Write a proposed change-review record for moving a point to another database reference. Include old/new identity, model artifact, validation, cache invalidation and rollback criteria. Classify proposed CRUD operations by their effect on graph metadata versus stored history; do not perform them. Contrast graph discovery with the subsequent bounded SQL read.

## Experiment

Compare an offline query result shape with the documented HTTP wrapper. If the app is unavailable, record the HTTP comparison as not run. Explain a stale-cache scenario using two paper model revisions.

## Acceptance checks

- Your design prevents a reader from mixing half-applied reference changes.
- The read-only boundary and distinct datasets are explicit.
- No implemented graph-write API, revision token or production deployment is invented.
- Proposed deletion of metadata is not described as automatic deletion of history.

## Stretch and reflection

What coordinated failure could occur between publishing a graph and provisioning a store key? Identify the validation that would prevent advertising an unreadable reference.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day55/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-8) for exact language and domain details.

[Previous: Day 54](day54.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 56](day56.md)
