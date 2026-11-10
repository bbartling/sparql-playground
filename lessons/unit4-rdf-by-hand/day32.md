# Day 32 — OWL properties: how things relate

**Goal:** know the three kinds of OWL property, and the five property types that let a reasoner fill in triples
you didn't write: sub-property, inverse, symmetric, transitive and functional. Then a quick look at property chains.

## Read

**OWL** ([OWL 2 Primer](https://www.w3.org/TR/owl2-primer/)) adds more precise words on top of RDFS. Today is all
about properties. Each one below has a burger example in the ontology, and what it means for buildings.

**Three kinds of property.**

| OWL | Links a thing to... | Burger Barn | Logic? |
|---|---|---|---|
| `owl:ObjectProperty` | another **thing** | `bb:hasPoint`, `bb:partOf` | yes |
| `owl:DatatypeProperty` | a **value** (literal) | `bb:oilSetpointC 175.0`, `bb:hasCalories 320` | yes |
| `owl:AnnotationProperty` | a note **for people** | `rdfs:label`, `rdfs:comment`, `skos:definition` | **none** |

Annotations carry no logic: a reasoner never infers anything from a label or a definition. They are for readers.

> **Buildings box.** `brick:hasPoint` is an object property (equipment → point). A setpoint's *value* is a
> datatype property (`brick:value 21.5`). `rdfs:label` and `skos:definition` are how **Brick** documents every
> class: annotations.

**`rdfs:subPropertyOf`: one property is a special case of another.** `bb:cookedOn` and `bb:storedIn` are both
kinds of `bb:usesEquipment`. "Crispy chicken is cooked on Fryer_1" means "crispy chicken uses Fryer_1".

> **Buildings box.** **Brick**'s `brick:feedsAir` is a sub-property of `brick:feeds`. Ask for `brick:feeds` and
> a reasoner (or the path `?p rdfs:subPropertyOf* brick:feeds`) also finds the air connections.

**`owl:inverseOf`: the same link, read backwards.** `bb:usesEquipment` / `bb:isUsedBy`, and
`bb:hasPoint` / `bb:isPointOf`. Write one direction; the other follows.

> **Buildings box.** **Brick** declares the pairs `brick:hasPoint` / `brick:isPointOf`, `brick:feeds` /
> `brick:isFedBy` and `brick:hasPart` / `brick:isPartOf`. **Haystack**'s `equipRef` on a point is the
> `isPointOf` direction.

**`owl:SymmetricProperty`: works both ways by definition.** If fries share a fryer with crispy chicken, crispy
chicken shares a fryer with fries. Also `bb:adjacentTo` between rooms.

> **Buildings box.** "Room 101 is next to room 102" is symmetric. Core **Brick** has no adjacency relationship,
> so a model that needs one adds it in its own extension (Week 8 shows how) and declares it symmetric: one triple
> per pair instead of two.

**`owl:TransitiveProperty`: chains add up.** The kitchen is part of the restaurant, the restaurant is part of the
North franchise region, so the kitchen is part of the region. Also `bb:contains`.

> **Buildings box.** A room is part of a floor, which is part of a building: **Brick**'s `brick:hasPart` /
> `brick:isPartOf`, which Brick's designers describe as transitive. And air flows AHU → VAV → zone through `brick:feeds`; "everything downstream of AHU_1" is
> `brick:feeds+` (Day 35).

**`owl:FunctionalProperty`: at most one value.** A menu item has exactly one calorie number; a fryer has one serial
number. If the data gives two, OWL doesn't flag it: it concludes the two must be *the same* value, which for two
different numbers means the data is inconsistent. In practice you check it with a query (`GROUP BY ... HAVING
(COUNT(...) > 1)`, which the script does) or a SHACL `sh:maxCount 1` (Day 35).

> **Buildings box.** One `brick:hasUnit` per point, one serial number per controller: functional in meaning,
> checked with SHACL in practice.

**Property chains, briefly.** `owl:propertyChainAxiom ( bb:hasIngredient bb:usesEquipment )` defines
`bb:needsEquipment`: a burger has a beef patty, the patty uses the grill, so the burger *needs* the grill. The
property path `bb:hasIngredient/bb:usesEquipment` asks the same thing without a reasoner.

[`day32_rdf.py`](day32_rdf.py) lists the properties by kind and type, then asks six questions three ways: a plain
query, a property path (no reasoner), and the plain query again after `owlrl` has added what the OWL rules entail.

## Run

```bash
uv run python lessons/course.py run 32
```

```
ObjectProperty (16): adjacentTo, contains, cookedOn, hasAlarm, hasIngredient, hasPoint, includes, isPointOf, isUsedBy, locatedIn, needsEquipment, partOf, servesItem, sharesFryerWith, storedIn, usesEquipment
DatatypeProperty (12): airSetpointC, fryTime, hasCalories, isOpen, lastInspected, oilSetpointC, openedOn, opensAt, seats, serialNumber, specialty, unit
AnnotationProperty (3): comment, definition, label
TransitiveProperty: ['contains', 'partOf']
SymmetricProperty: ['adjacentTo', 'sharesFryerWith']
FunctionalProperty: ['hasCalories', 'serialNumber']
Menu items with two calorie numbers: []

Triples: before inference 241 | after 783

subPropertyOf: what does CrispyChicken use?
  plain query, before inference: []
  property path, no inference:   ['Fryer_1', 'WalkInCooler_1']
  plain query, after inference:  ['Fryer_1', 'WalkInCooler_1']

inverseOf: who uses Fryer_1?
  plain query, before inference: []
  property path, no inference:   ['CrispyChicken', 'Fries']
  plain query, after inference:  ['CrispyChicken', 'Fries']

inverseOf: whose point is the oil temp?
  plain query, before inference: []
  property path, no inference:   ['Fryer_1']
  plain query, after inference:  ['Fryer_1']

symmetric: who shares a fryer with CrispyChicken?
  plain query, before inference: []
  property path, no inference:   ['Fries']
  plain query, after inference:  ['Fries']

transitive: what is MainKitchen part of?
  plain query, before inference: ['BurgerBarn']
  property path, no inference:   ['BurgerBarn', 'NorthRegion']
  plain query, after inference:  ['BurgerBarn', 'NorthRegion']

chain: what equipment does ClassicBurger need?
  plain query, before inference: []
  property path, no inference:   ['Grill_1', 'WalkInCooler_1']
  plain query, after inference:  ['Grill_1', 'WalkInCooler_1']
```

Every plain query is empty (or short) before inference and complete after, and the property path gets the same
answer with no reasoner at all. The reasoner more than triples the graph to get there.

## How this maps to buildings

> **Buildings box.** The boxes above, in one list:
>
> - **object / datatype / annotation:** `brick:hasPoint` / `brick:value` / the `skos:definition` on every
>   **Brick** class
> - **sub-property:** `brick:feedsAir` is a kind of `brick:feeds`
> - **inverse:** `brick:hasPoint` / `brick:isPointOf`, `brick:feeds` / `brick:isFedBy`; **Haystack**'s `equipRef`
> - **symmetric:** room adjacency, in your own extension
> - **transitive:** `brick:hasPart` / `brick:isPartOf`
> - **functional:** one unit or serial number per point, checked with SHACL
>
> **ASHRAE 223P** uses the same OWL property machinery for its connections, and checks them with SHACL.

## Why it matters

These five property types are most of what building ontologies use. Knowing them, you can read Brick's property
definitions and know which triples a tool will fill in for you, and which you must write.

## Try it

1. Delete `owl:SymmetricProperty` from `bb:sharesFryerWith` and re-run. Which "after" answer changes?
2. Which is easier to explain to a colleague: `bb:MainKitchen bb:partOf+ ?x` or "run the reasoner first"?
3. **Mini challenge (Burger Barn):** with only a property path (no reasoner), list everything that is part of the
   North region, at any depth.

<details><summary>Answers</summary>

1. "who shares a fryer with CrispyChicken?" after inference becomes `[]`; the path still finds Fries, because
   `^` reads the triple backwards whatever the ontology says.
2. A matter of taste. The path is explicit and needs nothing extra; the reasoner keeps every query short.
3. **BurgerBarn, DiningRoom, MainKitchen**: `SELECT ?part WHERE { ?part bb:partOf+ bb:NorthRegion }`.
   (The course's tests check this answer.)

</details>
