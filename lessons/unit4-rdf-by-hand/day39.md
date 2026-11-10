# Day 39 — Step 8: test the ontology with its competency questions and SHACL

**Goal:** turn Day 36's competency questions into SPARQL, run them on the restaurant, and validate the data with
SHACL rules kept in their own file.

## Read

The last step of Ontology Development 101 is testing. You have two kinds of test:

1. **Competency questions as SPARQL.** Each Day 36 question becomes a query. If a query can't be written, a term is
   missing (go back to step 3); if it returns nothing, a fact is missing (step 7). For example, CQ1:

   ```sparql
   SELECT DISTINCT ?item WHERE {
     ?item a burger:MenuItem ; burger:hasIngredient*/burger:cookedOn ?equipment .
     ?equipment a burger:Fryer .
   }
   ```

2. **SHACL shapes** for the closed-world checks the ontology can't do (Day 33). They live in
   [`burger_shapes.ttl`](burger_shapes.ttl), **separate from the ontology**: the ontology says what terms *mean*
   and anyone may reuse it; the shapes say what *this* kind of data file must contain, and different projects can
   have different shapes for the same ontology. Today's: every fryer has a temperature point and one decimal
   setpoint, every piece of equipment has a location (and, as a warning, a label), every menu item has one
   whole-number calorie count.

[`day39_rdf.py`](day39_rdf.py) runs all five questions, lists any without an answer, then validates.

## Run

```bash
uv run python lessons/course.py run 39
```

```
CQ1 Which menu items depend on a fryer?
   [('Fries',), ('OnionRings',)]
CQ2 Which equipment has no temperature sensor?
   [('Cooler_1',)]
CQ3 Where is each piece of equipment?
   [('Cooler_1', 'Kitchen_1'), ('Fryer_1', 'Kitchen_1'), ('Fryer_2', 'Kitchen_1'), ('Grill_1', 'Kitchen_1')]
CQ4 What oil temperature is each fryer set to?
   [('Fryer_1', '175.0'), ('Fryer_2', '180.0')]
CQ5 How many calories is each menu item?
   [('ClassicBurger', '540'), ('Cola', '150'), ('Fries', '320'), ('OnionRings', '410')]

Unanswered questions: []
Data follows the shapes: True
```

Every question answered, and the data passes the shapes. CQ2 is worth a second look: the walk-in cooler has no
temperature sensor. The shapes allow that (only fryers must have one). Whether they *should* is a design decision,
and today's mini challenge makes it.

## How this maps to buildings

> **Buildings box.** This is how an FDD model gets accepted: run the rule-input questions ("every AHU's supply-air
> temperature sensor") as SPARQL, run the **Brick** or **ASHRAE 223P** SHACL shapes plus your project's own, and
> only then switch the rules on. **Haystack** projects do the same with tag queries and their validation tools.

## Why it matters

"Done" for an ontology means: every competency question has a query that answers it, and real data passes the
shapes. Both are scripts, so you can re-run them on every change.

## Try it

1. Delete `burger:oilSetpoint 180.0` from `site:Fryer_2`. What changes in CQ4, and in the SHACL result?
2. Add a sixth competency question, "Which kitchen is each fryer in?", and its query.
3. **Mini challenge (Burger Barn):** write a shape that requires every walk-in cooler to have a point. Which
   cooler breaks it?

<details><summary>Answers</summary>

1. CQ4 loses Fryer_2, and SHACL fails: "A fryer needs exactly one decimal oil setpoint."
2. `SELECT ?fryer ?kitchen WHERE { ?fryer a burger:Fryer ; burger:hasLocation ?kitchen . ?kitchen a burger:Kitchen }`
3. **Cooler_1**:

   ```turtle
   burger:CoolerShape a sh:NodeShape ;
       sh:targetClass burger:WalkInCooler ;
       sh:property [ sh:path burger:hasPoint ; sh:minCount 1 ] .
   ```

   (The course's tests check this answer.)

</details>
