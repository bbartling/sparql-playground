# Daily SQL and database engineering course

[Course overview](README.md) · [Local lab](LAB_GUIDE.md) · [Remote lab](REMOTE_SETUP.md) · [Schema picture](SCHEMA.md) · [Glossary](GLOSSARY.md) · [Data contract](CONTRACT.md) · [References](SOURCES.md)

**84 days, 12 weeks.** Study six days, then attempt one independent weekly challenge. Allow 45–75 minutes per ordinary day and 2–4 hours per challenge, spread across evenings if useful. Progress by understanding, not a calendar deadline.

## Before Day 1

Choose [local Docker](LAB_GUIDE.md#route-a--isolated-lab-on-this-computer) or [a remote test-lab machine](REMOTE_SETUP.md). Both run PostgreSQL with Timescale available; early lessons teach ordinary PostgreSQL, and week 10 uses the extension deliberately. Use only the dedicated `brickts_course` database.

## How to study

1. Read the goal and concept; predict the tiny example before running it.
2. Type and change SQL yourself. Save it under ignored `student-work/sql/dayNN/`.
3. Explain the output grain, scope, units, time window and missing-data policy.
4. Finish the acceptance checks. Ask an AI for a hint or a review of your attempt, not the weekly solution.
5. Mark a day complete only after you can explain one corrected mistake. Label evidence observed, fixture-only or not run.

The weekly challenges provide requirements and acceptance criteria without a worked implementation. Reference SQL is a validation aid: attempt your own calculation first. [The lab guide](LAB_GUIDE.md#daily-evidence-and-weekly-rubric) contains a reusable review rubric.

## Course map and progress

### Week 1 — First SQL questions

SELECT, filters, NULL, sorting and summaries.

- [ ] [Day 01 — Open the SQL workbench](day01.md)
- [ ] [Day 02 — Read tables and name the row](day02.md)
- [ ] [Day 03 — Filter rows with explicit logic](day03.md)
- [ ] [Day 04 — Order results and take a bounded look](day04.md)
- [ ] [Day 05 — Count missing values before averaging](day05.md)
- [ ] [Day 06 — Group samples into accountable summaries](day06.md)
- [ ] [Day 07 — Week 1 challenge — the first site report](day07.md)

### Week 2 — Design trustworthy tables

Types, keys, relationships, joins and replay-safe inserts.

- [ ] [Day 08 — Choose a grain and a dependable key](day08.md)
- [ ] [Day 09 — Create a small table with useful constraints](day09.md)
- [ ] [Day 10 — Separate facts and enforce relationships](day10.md)
- [ ] [Day 11 — Join metadata and preserve empty groups](day11.md)
- [ ] [Day 12 — Detect a join that multiplies observations](day12.md)
- [ ] [Day 13 — Make repeated ingest safe in a transaction](day13.md)
- [ ] [Day 14 — Week 2 challenge — design a small relational schema](day14.md)

### Week 3 — Make time explicit

UTC, half-open windows, CTEs, gaps, coverage and pivots.

- [ ] [Day 15 — Query UTC instants with half-open windows](day15.md)
- [ ] [Day 16 — Use CTEs to make query stages readable](day16.md)
- [ ] [Day 17 — Add window calculations without collapsing rows](day17.md)
- [ ] [Day 18 — Compare neighboring observations with LAG and LEAD](day18.md)
- [ ] [Day 19 — Bound valid coverage instead of bridging gaps](day19.md)
- [ ] [Day 20 — Build explicit conditional summaries and pivots](day20.md)
- [ ] [Day 21 — Week 3 challenge — a time-series quality report](day21.md)

### Week 4 — Write safe application SQL

Transactions, parameters, migrations, roles and plans.

- [ ] [Day 22 — Observe commits, rollbacks, and a competing writer](day22.md)
- [ ] [Day 23 — Bind query values with SQL PREPARE](day23.md)
- [ ] [Day 24 — Change a schema with a reviewable migration](day24.md)
- [ ] [Day 25 — Inspect privileges and the limits of a row policy](day25.md)
- [ ] [Day 26 — Read an execution plan and justify an index](day26.md)
- [ ] [Day 27 — Turn assumptions into reviewable SQL checks](day27.md)
- [ ] [Day 28 — Week 4 challenge — a reviewable ingest schema](day28.md)

### Week 5 — Calculate runtime and energy

Cadence, duration, power integration, weekly reports.

- [ ] [Day 29 — Measure quality before calculating performance](day29.md)
- [ ] [Day 30 — Turn irregular samples into bounded intervals](day30.md)
- [ ] [Day 31 — Distinguish fan command from observed status](day31.md)
- [ ] [Day 32 — Calculate runtime with SQL and explicit unknown time](day32.md)
- [ ] [Day 33 — Integrate kW into observed kWh](day33.md)
- [ ] [Day 34 — Group reporting periods in each site’s timezone](day34.md)
- [ ] [Day 35 — Week 5 independent challenge — an observed runtime and energy report](day35.md)

### Week 6 — Explain HVAC analytics

Comfort, mixed air, weather, bins and engineering assumptions.

- [ ] [Day 36 — Choose the denominator for comfort percentage](day36.md)
- [ ] [Day 37 — Use mixing mathematics with physical eligibility checks](day37.md)
- [ ] [Day 38 — Keep BAS and web weather as separate sources](day38.md)
- [ ] [Day 39 — Weight aggregates and define a scatter dataset](day39.md)
- [ ] [Day 40 — Read the shape of fan and temperature relationships](day40.md)
- [ ] [Day 41 — Save query results without hiding freshness or detail](day41.md)
- [ ] [Day 42 — Week 6 independent challenge — an analytics engineering review](day42.md)

### Week 7 — Build defensible fault detection

Masks, applicability, startup, streaks, tuning and evidence.

- [ ] [Day 43 — Express a fault predicate without turning unknown into healthy](day43.md)
- [ ] [Day 44 — Confirm consecutive candidates with gap-aware islands](day44.md)
- [ ] [Day 45 — Gate rules by mode and allow startup time](day45.md)
- [ ] [Day 46 — Bound the rule window and retrieve enough context](day46.md)
- [ ] [Day 47 — Separate rule applicability from per-equipment tuning](day47.md)
- [ ] [Day 48 — Preserve raw evidence beside confirmed fault summaries](day48.md)
- [ ] [Day 49 — Week 7 independent challenge — a known-answer pressure FDD report](day49.md)

### Week 8 — Use RDF and SPARQL practically

Brick equipment discovery and external timeseries references.

- [ ] [Day 50 — Read the small amount of RDF your SQL workflow needs](day50.md)
- [ ] [Day 51 — Discover typed equipment with a small SELECT](day51.md)
- [ ] [Day 52 — Follow point ownership through an equipment part tree](day52.md)
- [ ] [Day 53 — Resolve a point reference before a bounded SQL read](day53.md)
- [ ] [Day 54 — Build an explicit Brick-to-rule adapter](day54.md)
- [ ] [Day 55 — Review graph changes and inspect the read-only web boundary](day55.md)
- [ ] [Day 56 — Week 8 independent challenge — a model-driven SQL analytics report](day56.md)

### Week 9 — Keep APIs and queries fast

Plans, indexes, pagination, plot envelopes and concurrency.

- [ ] [Day 57 — Read an execution plan before adding an index](day57.md)
- [ ] [Day 58 — Page history with a stable cursor](day58.md)
- [ ] [Day 59 — Write a parameterized history and plot contract](day59.md)
- [ ] [Day 60 — Bound database concurrency and prove cancellation](day60.md)
- [ ] [Day 61 — Make ingest retries idempotent](day61.md)
- [ ] [Day 62 — Budget a bounded history workload](day62.md)
- [ ] [Day 63 — Independent challenge — a fast, bounded history API design](day63.md)

### Week 10 — Operate PostgreSQL and Timescale

Chunks, aggregation, retention, backups and resource budgets.

- [ ] [Day 64 — Create a time-partitioned scratch hypertable](day64.md)
- [ ] [Day 65 — Measure chunk pruning and time buckets](day65.md)
- [ ] [Day 66 — Track continuous aggregate freshness](day66.md)
- [ ] [Day 67 — Review retention and columnstore as data lifecycle changes](day67.md)
- [ ] [Day 68 — Budget database memory and avoid full-history fetches](day68.md)
- [ ] [Day 69 — Measure bounded scale with declared limits](day69.md)
- [ ] [Day 70 — Independent challenge — a Timescale performance report](day70.md)

### Week 11 — Test like a database engineer

Independent answers, mutations, scope, replay and stress.

- [ ] [Day 71 — Assert known answers and test the tests](day71.md)
- [ ] [Day 72 — Test scope, constraints and row security negatively](day72.md)
- [ ] [Day 73 — Observe transactions, locks and bounded deadlock recovery](day73.md)
- [ ] [Day 74 — Freeze model revisions and copy runs consistently](day74.md)
- [ ] [Day 75 — Check installed schema against a versioned manifest](day75.md)
- [ ] [Day 76 — Replay a small failure qualification matrix](day76.md)
- [ ] [Day 77 — Independent challenge — an honest stress qualification packet](day77.md)

### Week 12 — Read Open-FDD with confidence

77-rule catalog, 18 analytics queries and a reviewed capstone.

- [ ] [Day 78 — Trace the production SQL input boundary](day78.md)
- [ ] [Day 79 — Inventory all 77 rules and the separate analytics pack](day79.md)
- [ ] [Day 80 — Audit and exercise the complete FC1 diagnostic](day80.md)
- [ ] [Day 81 — Separate a SQL metric from a runtime analytics query](day81.md)
- [ ] [Day 82 — Package a portable API and Plotly figure with provenance](day82.md)
- [ ] [Day 83 — Review a migration and an execution test plan](day83.md)
- [ ] [Day 84 — Independent capstone — specify model-driven SQL FDD and analytics](day84.md)

## Graduation evidence

A fresh installation and safe migration; a scoped relational schema; known-answer runtime, energy and fault reports; graph-to-SQL identity checks; small plot-ready API contracts; measured bounded stress; and a source review of real Open-FDD SQL. The capstone tests a representative diagnostic and metric plus analytics; it does not claim all 77 production rules have been implemented by the student.

No production or engineering certification is implied. The goal is to make database behavior explainable and testable so you can work confidently with real systems.
