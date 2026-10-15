# Day 63 — Independent challenge — a fast, bounded history API design

[Previous: Day 62](day62.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 64](day64.md)

**Week 9 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 57–62, or equivalent skills.

## Project brief

Produce a reviewable SQL and API design for a historian read path. A caller selects an authorized site and RDF point, requests a finite interval, and receives raw or aggregated plot data. Reuse the fixture and your earlier experiments. Implement SQL and contract artifacts; an application UI or new running service is unnecessary.

This is an independent assessment. Choose your own decomposition and use earlier lessons and [primary references](SOURCES.md#week-9) as references after outlining your approach.

## Acceptance criteria

- Identity resolves through model metadata to opaque UUIDs; site authorization covers both resolution and SQL.
- Parameterized query contracts cap time span, points, rows, queue and execution time.
- Pagination has deterministic ordering and declared consistency semantics.
- Plots retain units, quality, gaps, query/model versions and coverage.
- Measured plans support index choices, and cancellation evidence includes transaction cleanup.
- Duplicate ingest and database unavailability have bounded, observable outcomes.

## Deliverables

Submit SQL, sample request/response documents, one plan comparison, a small workload table and an error matrix. Include empty, wrong-site, duplicate and timeout cases. Keep tests within two clients and forty requests. Label results **observed**, **fixture-only** or **not run**.

## Self-review

What work can still grow despite a response limit? Which measurements support your claimed latency? What happens when a client abandons a request? Explain one limitation that would require a new experiment before production use.

[Previous: Day 62](day62.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 64](day64.md)
