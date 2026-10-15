# Day 51 — Discover typed equipment with a small SELECT

[Previous: Day 50](day50.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 52](day52.md)

**Week 8 · 45–75 minutes.** Prerequisites: Days 1–50, or equivalent SQL skills.

## Goal

Find equipment by an explicit Brick class and preserve its identity across the graph-to-SQL boundary.

## Before you start

Run `uv run python lessons/sql/graph_lab.py lessons/sql/sparql/day51_ahus.rq`. The helper loads only the course instance graph. It does not load the Brick ontology or infer class hierarchies.

## Concept

A basic SPARQL pattern resembles a join: repeated variables require matching RDF terms. `?equipment a brick:Air_Handler_Unit` matches that explicitly asserted class. Add label and site patterns to retrieve context, then use `SELECT` to choose output columns. `ORDER BY` makes a result easier to compare; it does not create a meaningful identity.

An exact class match is not the same as asking for every subclass of a broad class. The course graph has no `rdfs:subClassOf` closure, so a broad `brick:Equipment` query may return nothing even when explicit AHUs exist. Applications that depend on subclass discovery must explicitly load/query the necessary ontology or inference behavior. This course baseline keeps that boundary visible.

## Tiny example

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
SELECT ?equipment
WHERE { ?equipment a brick:Air_Handler_Unit }
ORDER BY ?equipment
LIMIT 10
```

The supplied query additionally returns site, label and the explicit equipment UUID literal. It is a discovery example, not a report of measured operation.

## SQL challenge

Write your own graph inventory query returning equipment IRI, explicit UUID field, site and label. Compare its rows with a SQL inventory over `course.equipment`. Demonstrate that labels alone cannot join the two inventories safely. Keep IRI and UUID fields separately named in your evidence.

## Experiment

Replace the class in your copied query with `brick:Equipment`. Predict the instance-only result before running. Explain why an empty exact-class result is not proof that the building has no equipment. Restore the explicit AHU class.

## Acceptance checks

- AHU discovery returns three rows: two north, one south.
- Supply A appears twice with different site and equipment identities.
- Graph and SQL inventories agree through explicit UUID fields.
- Your note states that subclass inference is absent in this helper.

## Stretch and reflection

What is the minimum additional metadata needed to query all fan subtypes reliably? Describe the requirement without expanding this lab into an ontology-authoring project.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day51/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-8) for exact language and domain details.

[Previous: Day 50](day50.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 52](day52.md)
