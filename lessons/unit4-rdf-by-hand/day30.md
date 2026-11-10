# Day 30 — SPARQL checks: what's missing?

**Goal:** use `FILTER NOT EXISTS`, `!BOUND` and `STRLEN` to find missing points, missing labels and blank labels.

## Read

The most useful questions about a model are often about what is **not** there. SPARQL has two ways to ask:

| Question | SPARQL | How it works |
|---|---|---|
| fryers with no temperature point | `FILTER NOT EXISTS { ?fryer bb:hasPoint ?p . ?p a bb:TemperatureSensor }` | keep the row only if the inner pattern finds nothing |
| equipment with no label | `OPTIONAL { ?e rdfs:label ?l } FILTER(!BOUND(?l))` | the optional part left `?l` empty |
| equipment with a blank label | `?e rdfs:label ?l . FILTER(STRLEN(?l) = 0)` | the label exists but has zero characters |

[`day30_rdf.py`](day30_rdf.py) runs all three.

## Run

```bash
uv run python lessons/course.py run 30
```

```
Fryers with no temperature point: ['Fryer_2']
Kitchen equipment with no label at all: ['IceMachine_1']
Kitchen equipment with a blank label: ['WalkInCooler_1']
```

Fryer_2, the ice machine and the walk-in cooler: three different mistakes, three different queries. This is
**closed-world** checking: "if it isn't written down, it's missing". That sounds obvious, but Week 7 shows that OWL
reasons the other way (open world), and Day 35 turns these queries into SHACL rules, the standard way to write
closed-world checks.

## How this maps to buildings

> **Buildings box.** "VAVs without a zone temperature sensor", "points with no unit", "equipment with no
> label": these are the first checks anyone runs on a new **Brick** or **Haystack** model, and they are the
> same `FILTER NOT EXISTS` queries. **ASHRAE 223P** and Brick ship these kinds of rules as SHACL shapes, so a
> tool can check a model before an FDD rule trusts it.

## Why it matters

An FDD rule that silently skips the AHU with no supply-air temperature looks like "no faults". A check like today's
turns that silence into a to-do list.

## Week 6 further reading

- W3C, [RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/) and [RDF 1.1 Turtle](https://www.w3.org/TR/turtle/)
- W3C, [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/) (sections 2–5 and 8 cover this week)
- W3C, [XML Schema datatypes](https://www.w3.org/TR/xmlschema11-2/) (just the table of built-in types)
- [rdflib documentation](https://rdflib.readthedocs.io/)

## Try it

1. Give Fryer_2 a temperature point in `burger_barn.ttl` (a new `bb:Fryer_2_OilTemp a bb:TemperatureSensor`).
   Which list empties?
2. Why doesn't `FILTER(!BOUND(?l))` find the walk-in cooler?
3. **Mini challenge (Burger Barn):** which points have no `bb:unit`? (Look at points linked with `bb:hasPoint`
   or `bb:hasAlarm`.)

<details><summary>Answers</summary>

1. "Fryers with no temperature point" becomes `[]`.
2. The cooler *has* a label triple, so `?l` is bound (to `""`). Only `STRLEN` sees that it's empty.
3. **`Cooler_DoorAlarm`**, which is fair: a door alarm is open or closed and has no unit.

   ```sparql
   SELECT ?point WHERE {
     ?equipment bb:hasPoint|bb:hasAlarm ?point .
     FILTER NOT EXISTS { ?point bb:unit ?unit }
   }
   ```

   (The course's tests check this answer.)

</details>
