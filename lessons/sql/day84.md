# Day 84 — Independent capstone — specify model-driven SQL FDD and analytics

[Previous: Day 83](day83.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md)

**Week 12 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 78–83, or equivalent skills.

## Project brief

Deliver a coherent specification and executable SQL evidence for model-driven FDD and analytics. The read path must resolve RDF metadata to opaque historian identity, adapt roles/units explicitly, execute a full diagnostic and a separate metric/analytics query, and package bounded results with reproducible provenance. Choose your design independently; any API language may implement the contract.

Use the synthetic course database and pinned references in [Open-FDD bridge](OPENFDD_BRIDGE.md). This capstone demonstrates the proficiency evidenced by your artifacts; it does not confer a degree or guarantee production readiness.

## Acceptance criteria

- All 77 FDD entries and the separate analytics inventory have applicability and tuner/type metadata.
- One complete FC1 implementation and one metric/analytics query have independent known answers, timestamp/coverage evidence and negative tests.
- RDF resolution, site isolation, duplicate-role policy, unit conversion and immutable revisions are explicit.
- Parameterized SQL, bounded execution, pagination/aggregation, cancellation and resource budgets are reviewable.
- API/Plotly artifacts share a result cohort; schema/migration and qualification plans record remaining gaps honestly.

## Deliverables

Submit architecture and contract documents, SQL/DDL, inventory, assertions, compact plans/performance evidence, sample responses/figure JSON and a qualification ledger. Label observed, skipped, blocked and proposed work distinctly. Keep experiments within earlier limits.

## Self-review

Trace one result from model to plot. Defend its units, duration and authorization. Explain one production-source defect you caught and one unresolved requirement that prevents a stronger claim.

[Previous: Day 83](day83.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md)
