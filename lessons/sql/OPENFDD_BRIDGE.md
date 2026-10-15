# From course SQL to real Open-FDD source

[Course index](INDEX.md) · [Week12 starts on Day78](day78.md)

Reference pinned to Open-FDD **3.6.15 / a45832188ca35ef50987ea73e48c034706a45c86**. It is a source-reading target, not a claim that this version passes every equation, browser or operational gate. The committed [inventory](openfdd_inventory.json) lists 77 authored rules and 18 analytics SQL files with source URLs/hashes. Your local Open-FDD checkout is optional and read-only for this course; do not change its application data to finish a lesson.

## The layers you should be able to trace

1. A model identifies an equipment kind and its required points/roles/units.
2. Opaque timeseries keys resolve to the exact authorized history rows.
3. A schema/helper/input adapter constructs the SQL relations the authored query expects.
4. A validated window, warmup, cadence, confirmation and effective tuning render/bind the calculation.
5. SQL returns the declared result kind: fault interval/mask/elapsed time or metric fields.
6. A durable run/cohort records scope, input/model/config/SQL revisions and completeness.
7. A small API returns summaries first and one selected bounded plot, preserving actual masks and unknowns.
8. Independent expected results and tests check all those layers. Catalog/file visibility alone is not execution proof.

## Rule reading map

- [Registry: applicability/roles/tuners](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/fdd/registry.yaml)
- [Input contract](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/fdd/input_contract.sql)
- [Numeric template renderer](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/fdd/render_rule.py)
- [PostgreSQL helper functions](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/fdd/postgres_helpers.sql)
- [FC1: duct static, fan gates, startup/stability, confirmation](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/fdd/postgres/rules/fc1_duct_static_low.sql)
- [Fan runtime metric](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/fdd/postgres/rules/fan_runtime_hours.sql)
- [Average zone temperature metric](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/fdd/postgres/rules/avg_zone_temp.sql)
- [Runtime adapter](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/services/central/src/timescale_product.rs)

`{{CONFIRM_ROWS}}` is a template token, not SQL PostgreSQL can execute directly. A parameter renderer handles vetted numeric tuners; data identities/windows still need parameterized binding. An authored query reads a relation named history; it does not magically discover source roles or enforce every API authorization rule.

The course uses static<0.9*setpoint, observed fan status and a declared gap-aware three-row confirmation. That is deliberately smaller than production FC1. Production includes different tolerances, operational/mode gates, fan precedence and coverage rules. Course 0/1 fan_status is not an automatic substitute for every source command convention. The inventory's confirm_seconds and role names are evidence to inspect, not a license to silently convert seconds to minutes or guess source units.

Read current SQL critically: row-count confirmation can bridge missing timestamps unless an input adapter breaks gaps. A runtime query that counts both command and status can double-count a motor. A final LIMIT can hide full-history input work. Identify, reproduce and test these assumptions instead of treating public code as an unquestionable golden answer.

## Analytics reading map

- [Analytics registry](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/analytics/registry.json)
- [All query bodies](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/analytics/postgres/queries)
- [Motor weekly runtime](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/analytics/postgres/queries/motor_weekly_runtime.sql)
- [Mechanical cooling OAT bins](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/analytics/postgres/queries/mechanical_cooling_oat_bins.sql)
- [Economizer deltas](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/analytics/postgres/queries/economizer_deltas.sql)
- [Adapter and response contracts](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/services/central/src/timescale_analytics.rs)
- [Core schema files](https://github.com/bbartling/open-fdd/blob/a45832188ca35ef50987ea73e48c034706a45c86/sql/schema)

Build a review matrix for every inventory entry: input grain, units, exact scope/window, parameter defaults, missing/quality policy, grouping/joins, output kind and a useful failure case. You need not rewrite 77 rules in a weekend. The graduation skill is to trace any one without fear and explain what would prove its correctness. Implement and independently verify a representative diagnostic and a metric plus runtime/energy analytics before calling your capstone complete.

## Where Brick and SPARQL fit

This playground uses Brick. The production reference uses a Haystack RDF profile and application extensions. They are not interchangeable namespaces or one ontology. Both can support the same boundary: ask a semantic graph for the intended point, validate its unique external binding, then query exact SQL history. Keep units, source quality and model revision explicit. Changing a label must not change historian identity.

The graph describes meaning and connectivity; PostgreSQL computes on samples. High-level SELECT/ASK and external-reference lookup are enough for this course. Deep OWL reasoning is optional. A future energy/twin workflow may consume the same identities and engineering quantities, but must keep measured and simulated records distinguishable.

## Final professional review

Before approving a change, demonstrate a fresh schema install, a safe upgrade, independent known answers, exact multi-site/equipment isolation, parameter validation, null/gap handling, bounded queries, coherent run identity and honest failure reporting. Use pandas only as an optional independent oracle/test helper; shared authored calculations remain SQL. The course does not certify an actual building, savings claim or security assessment.
