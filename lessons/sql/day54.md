# Day 54 — Build an explicit Brick-to-rule adapter

[Previous: Day 53](day53.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 55](day55.md)

**Week 8 · 45–75 minutes.** Prerequisites: Days 1–53, or equivalent SQL skills.

## Goal

Separate graph semantics, course role names, units and production rule inputs before comparing FDD behavior.

## Before you start

Read [the Open-FDD bridge](OPENFDD_BRIDGE.md), including its pinned reference and distinction between this repository's Brick profile and Open-FDD's Haystack conventions and extensions. Run `uv run python lessons/sql/graph_lab.py lessons/sql/sparql/day54_role_units.rq`.

## Concept

Brick classes describe equipment and point meaning using RDF relationships. Haystack represents semantic information through its own tags, definitions and relationships. Open-FDD also has a specific rule-input contract. A role string such as `duct_static` is a local adapter key, not proof that every system uses that exact name or unit.

An adapter must map identity, signal meaning, unit, timestamps, quality and required input names. Pressure in Pa cannot be sent as an assumed value in another pressure unit. A numeric percentage cannot become a Boolean merely by renaming the column. A measured fan status is not a fan command. The rule catalog and pinned implementation determine which signal the production rule actually requires.

## Tiny example

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX ex: <https://example.org/course#>
SELECT DISTINCT ?role ?unit
WHERE { ?point ex:role ?role ; brick:hasUnit ?unit }
ORDER BY ?role
```

This inventories fourteen local role/unit pairs. It does not establish production rule applicability or perform unit conversion.

## SQL challenge

Write a scratch adapter table or documented mapping for pressure, pressure setpoint, fan status and fan-speed command. Include course role, Brick class, QUDT unit, candidate production input and required transformation or unresolved question. Use SQL metadata to audit presence and units before constructing any rule-ready result.

## Experiment

Describe how your adapter rejects a scratch pressure value labelled kPa when Pa is expected. Then test a deliberate status-versus-command mismatch in scratch mapping metadata. A failed audit is the expected evidence; do not silently relabel the signal to make a rule run.

## Acceptance checks

- Role/unit inventory has fourteen pairs, including Pa, kW, °C, percent and unitless status.
- Mapping retains status and command as distinct signals.
- Unsupported units or ambiguous source roles block adapter success with a reason.
- Your report calls the Week 7 predicate a teaching rule and identifies what must be checked before production comparison.

## Stretch and reflection

Would two correctly mapped implementations necessarily return identical faults if their startup and confirmation policies differ? Explain which policy metadata belongs beside any comparison.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day54/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-8) for exact language and domain details.

[Previous: Day 53](day53.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 55](day55.md)
