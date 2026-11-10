# Day 37 — Steps 4–5: classes, hierarchy and properties

**Goal:** read the classes and properties of the new Burger ontology, [`burger.ttl`](burger.ttl), and check that
every term the competency questions need is defined, labelled and explained.

## Read

Steps 4 and 5 of Ontology Development 101 turn Day 36's term list into definitions. Open `burger.ttl`; every term
is written the same way:

```turtle
burger:Fryer a owl:Class ;
    rdfs:subClassOf burger:CookingEquipment ;
    rdfs:label "Fryer" ;
    skos:definition "A vat of hot oil that cooks food." ;
    rdfs:isDefinedBy <https://example.org/burger> .
```

| Line | Why |
|---|---|
| `a owl:Class` | it's a class (step 4) |
| `rdfs:subClassOf` | where it sits in the hierarchy |
| `rdfs:label` | what people call it |
| `skos:definition` | what it means, in one sentence. The most useful line for a reader. |
| `rdfs:isDefinedBy` | which ontology it belongs to |

The textbook's tips for step 4, in short: a subclass is a *kind of* its parent ("a fryer is a kind of cooking
equipment"; "a fryer basket is a kind of fryer" fails the test, so it's a part, not a subclass); keep siblings at
the same level of detail; and name classes in the singular.

For step 5, each property gets a kind (object or datatype, Day 32), a domain and a range. Remember Day 31: domain
and range let a reasoner *infer* types; they don't check anything.

[`day37_rdf.py`](day37_rdf.py) prints the class tree and the properties, then runs three quality checks: every term
from Day 36 is defined, and every term has a label and a definition.

## Run

```bash
uv run python lessons/course.py run 37
```

```
Classes (class, parent):
   CookingEquipment   Equipment
   Cooler             None
   Equipment          None
   Fryer              CookingEquipment
   Grill              CookingEquipment
   Ingredient         None
   Kitchen            Space
   MenuItem           None
   Point              None
   Restaurant         Space
   Space              None
   TemperatureSensor  Point
   WalkInCooler       Equipment

Properties (name, kind, domain, range):
   cookedOn       ObjectProperty     None         CookingEquipment
   hasIngredient  ObjectProperty     MenuItem     Ingredient
   hasLocation    ObjectProperty     Equipment    Space
   hasPoint       ObjectProperty     Equipment    Point
   isPointOf      ObjectProperty     None         None
   servesItem     ObjectProperty     Restaurant   MenuItem
   hasCalories    DatatypeProperty   MenuItem     integer
   oilSetpoint    DatatypeProperty   Fryer        decimal

Terms the competency questions need but burger.ttl lacks: []
Terms without a label: [] | without a definition: []
```

Three empty lists: nothing missing. `Cooler` has no parent: it's the deprecated old name for a walk-in cooler
(Day 43 explains). `isPointOf` has no domain or range of its own because it's the inverse of `hasPoint`, which has
both.

## How this maps to buildings

> **Buildings box.** Every **Brick** class has an `rdfs:label` and a `skos:definition` (look one up on
> [ontology.brickschema.org](https://ontology.brickschema.org/)), and **ASHRAE 223P** documents each class the same way.
> When you define your own terms for a site or a product, write the definition first: it's the line the next
> engineer reads.

## Why it matters

An undocumented term gets used three different ways by three people. One definition per term, checked by a script,
prevents that.

## Try it

1. Add `burger:Fryer` as a subclass of `burger:Grill` instead. What does the tree say, and why is it wrong?
2. Remove the `skos:definition` from `burger:Grill`. What does the script print?
3. **Mini challenge (Burger Barn):** add a `burger:IceMachine` class (a kind of `burger:Equipment`) with a
   label and a definition. How many classes are there now, and do the checks still pass?

<details><summary>Answers</summary>

1. `Fryer -> Grill`. A fryer isn't a kind of grill; both are kinds of cooking equipment.
2. `without a definition: ['Grill']`.
3. **14 classes**, and all three lists stay empty:

   ```turtle
   burger:IceMachine a owl:Class ; rdfs:subClassOf burger:Equipment ;
       rdfs:label "Ice machine" ; skos:definition "A machine that makes ice." .
   ```

   (The course's tests check this answer.)

</details>
