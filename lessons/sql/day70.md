# Day 70 — Independent challenge — a Timescale performance report

[Previous: Day 69](day69.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 71](day71.md)

**Week 10 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 64–69, or equivalent skills.

## Project brief

Assess whether a Timescale design improves a declared historian workload. Use SQL, measured plans and a reproducible report. Your dataset may contain at most 241,900 synthetic rows; concurrency is capped at two clients and the run has explicit deadlines. Choose the design and comparisons independently.

Consult [primary references](SOURCES.md#week-10) and installed signatures as needed. Missing Timescale support is a blocked requirement, not a successful plain-PostgreSQL substitute.

## Acceptance criteria

- Record PostgreSQL/extension versions, schema, unique key, chunk interval and indexes.
- Demonstrate selective time predicates and explain observed chunk pruning.
- Compare correct raw and continuous-aggregate answers, including a historical correction and freshness evidence.
- Measure a bounded columnstore comparison with matching result sets.
- Explain retention’s effect on raw history and refreshed aggregates.
- Report actual timing, source/result rows, payload measurements where available, failures and memory estimates with their assumptions.

## Deliverables

Submit SQL, a workload matrix, representative plans and a short recommendation tied to the workload. Include dataset generation limits and cleanup instructions. Label each result **observed**, **fixture-only**, **not run** or **blocked**. A tiny dataset showing no speedup is a valid finding.

## Self-review

Which cost moved into refresh or ingest? What does the test fail to model? Which measured result would change your recommendation? Explain how a stale summary could return a fast but unacceptable answer.

[Previous: Day 69](day69.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 71](day71.md)
