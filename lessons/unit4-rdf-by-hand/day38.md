# Day 38 — Steps 6–7: restrictions and instances

**Goal:** add restrictions to classes, describe one restaurant with the ontology, and keep the two in separate files.

## Read

**Step 6: restrictions.** A restriction says what every member of a class has. `burger.ttl` has two:

| Restriction | Reads | OWL words |
|---|---|---|
| on `Fryer` | every fryer has **some** temperature point | `owl:someValuesFrom burger:TemperatureSensor` |
| on `MenuItem` | every menu item has **exactly one** calorie number | `owl:cardinality 1` |

Others you'll see: `owl:allValuesFrom` (*only* this kind), `owl:minCardinality` / `owl:maxCardinality`. Remember
Day 33: under the open world, OWL uses these to *infer*, never to report something missing. A menu item with no
calories doesn't break the restriction to OWL. The shapes on Day 39 check that.

**Step 7: instances.** [`burger_site.ttl`](burger_site.ttl) describes one restaurant: two fryers, a grill, a
walk-in cooler, three sensors and four menu items. Note its *own* namespace, `site:`. The ontology (`burger:`) is
shared by every restaurant; each restaurant's facts live in their own file under their own names. That's the TBox /
ABox split from Day 31, made into two files and two namespaces.

[`day38_rdf.py`](day38_rdf.py) lists the restrictions, counts the instances per class, and checks that the
instances only use classes the ontology defines.

## Run

```bash
uv run python lessons/course.py run 38
```

```
Restrictions (class, property, rule):
   Fryer hasPoint some TemperatureSensor
   MenuItem hasCalories exactly 1

TBox: 125 triples | ABox: 52 triples
Instances per class: {'Fryer': 2, 'Grill': 1, 'Ingredient': 2, 'Kitchen': 1, 'MenuItem': 4, 'Restaurant': 1, 'TemperatureSensor': 3, 'WalkInCooler': 1}
Classes used in the ABox but not defined in the TBox: []
```

## How this maps to buildings

> **Buildings box.** **Brick** is one TBox shared by thousands of building models (ABoxes), each in its own
> namespace. **ASHRAE 223P** expresses most "every X has a Y" rules as SHACL shapes rather than OWL restrictions,
> because a building model needs them *checked*, not inferred. **Haystack** works the same way at heart: shared defs
> (the TBox) and per-site records (the ABox).

## Why it matters

Keeping the ontology and the data apart means you can publish one and share it, and load any restaurant (or
building) against it.

## Try it

1. Add a `burger:MenuItem` called `site:Shake` with no calories. Does the script complain? Will Day 39's SHACL?
2. Write a restriction "every kitchen is part of some restaurant" (you'd need a `burger:partOf` property first).
3. **Mini challenge (Burger Barn):** which menu items does `site:Restaurant_1` serve? Answer with SPARQL.

<details><summary>Answers</summary>

1. This script doesn't: open world, and the class is defined. Day 39's SHACL does: "A menu item needs exactly one
   whole-number calorie count."
2. `burger:Kitchen rdfs:subClassOf [ a owl:Restriction ; owl:onProperty burger:partOf ; owl:someValuesFrom burger:Restaurant ] .`
3. **ClassicBurger, Cola, Fries, OnionRings**:
   `SELECT ?item WHERE { site:Restaurant_1 burger:servesItem ?item . ?item a burger:MenuItem }`.
   (The course's tests check this answer.)

</details>
