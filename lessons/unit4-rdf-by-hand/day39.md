# Day 39 — Step 8: test the ontology with its competency questions and SHACL

**Goal:** turn Day 36's competency questions into SPARQL, run them on the restaurant, and validate the data with
SHACL rules kept in their own file. Then meet the other way to attach a rule: a class that is its own shape.

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

**Two ways to attach a shape.** The shapes above name their target: `sh:targetClass burger:Fryer`. There's a
second way. A class can *also be* an `sh:NodeShape`. SHACL then checks every instance of that class: an
*implicit class target*, no `sh:targetClass` needed. From [`burger_cook_methods.ttl`](burger_cook_methods.ttl):

```turtle
burger:FriedMenuItem a owl:Class, rdfs:Class, sh:NodeShape ;
    rdfs:subClassOf burger:MenuItem ;
    sh:property [
        sh:path burger:cookMethod ;
        sh:hasValue burger:CookMethod.fried ;   # exactly this named value (Day 38)
        sh:minCount 1 ;
        sh:maxCount 1 ;
    ] .
```

Compare the separate-file version, [`burger_cook_shapes.ttl`](burger_cook_shapes.ttl): a `burger:MenuItemCookShape`
with `sh:targetClass burger:MenuItem`, an `sh:in` list of the three cook methods, and a warning for labels that
don't start with a letter (Day 38's clean names).

| | Separate shapes file + `sh:targetClass` | Class is its own shape |
|---|---|---|
| Where the rule lives | next to the data project | inside the ontology |
| Who gets it | whoever loads that shapes file | everyone who loads the ontology |
| Good for | project rules ("our fryers need a setpoint"); different projects, different rules | rules that are part of what the class *means* ("a fried item is fried") |

Week 9 recommends separate files for your own project rules, and that still holds. Class-as-shape is the right pick
when the rule *is* the definition and should travel with the class. Big ontologies do it this way: most classes in
**Brick** 1.4 are `owl:Class, sh:NodeShape`, **ASHRAE 223P** declares its classes `s223:Class, sh:NodeShape`, and
the object types in the [csml2rdf BACnet ontology](https://github.com/JoelBender/csml2rdf/blob/main/bacnet.ttl) are
`rdfs:Class, sh:NodeShape`.

The SHACL spec's exact rule: the node must be an `rdfs:Class` *and* an `sh:NodeShape` in the shapes graph. That's
why `burger:FriedMenuItem` says `rdfs:Class` as well as `owl:Class` (pySHACL also accepts `owl:Class` on its own,
but saying both follows the spec to the letter).

[`day39_rdf.py`](day39_rdf.py) runs all five questions, lists any without an answer, then validates. Last, it
checks the cook-method data (with Day 38's three mistakes) both ways.

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

Cook-method check, separate file:
   FriedPickles Warning Keep labels clean: start with a letter, no codes like '15-' in front.
   Shake Violation A menu item needs exactly one cook method, one of the CookMethod values.

Cook-method check, class is shape:
   CrispyChicken Violation A fried menu item has exactly one cook method: CookMethod.fried.
```

Every question answered, and the data passes the shapes. CQ2 is worth a second look: the walk-in cooler has no
temperature sensor. The shapes allow that (only fryers must have one). Whether they *should* is a design decision,
and today's mini challenge makes it.

The two cook-method checks find different things. The separate file's `sh:in` list catches **Shake** (text, not a
named value) and warns about **FriedPickles**' coded label. The class-as-shape catches **CrispyChicken**: "grilled" is
a perfectly good cook method, so `sh:in` lets it through, but a *fried* menu item must be fried.

## How this maps to buildings

> **Buildings box.** This is how an FDD model gets accepted: run the rule-input questions ("every AHU's supply-air
> temperature sensor") as SPARQL, run the **Brick** or **ASHRAE 223P** SHACL shapes plus your project's own, and
> only then switch the rules on. **Haystack** projects do the same with tag queries and their validation tools.
>
> **Brick** and **223P** ship their rules as class-as-shape: load the ontology and `brick:Air_Handling_Unit` (an
> `owl:Class` *and* an `sh:NodeShape`) already checks its own instances. Your project's extra rules (this site's AHUs
> need a discharge-air sensor) go in a separate shapes file with `sh:targetClass`.

## Why it matters

"Done" for an ontology means: every competency question has a query that answers it, and real data passes the
shapes. Both are scripts, so you can re-run them on every change.

## Try it

1. Delete `burger:oilSetpoint 180.0` from `site:Fryer_2`. What changes in CQ4, and in the SHACL result?
2. Add a sixth competency question, "Which kitchen is each fryer in?", and its query.
3. Delete `owl:Class, rdfs:Class` from `burger:FriedMenuItem` (keep `sh:NodeShape`). Does CrispyChicken still fail?
4. **Mini challenge (Burger Barn):** write a shape that requires every walk-in cooler to have a point. Which
   cooler breaks it?

<details><summary>Answers</summary>

1. CQ4 loses Fryer_2, and SHACL fails: "A fryer needs exactly one decimal oil setpoint."
2. `SELECT ?fryer ?kitchen WHERE { ?fryer a burger:Fryer ; burger:hasLocation ?kitchen . ?kitchen a burger:Kitchen }`
3. No. It's still a shape, but no longer a class, so it has no implicit target and checks nothing. (pySHACL is
   lenient the other way: a class with `sh:property` but no `sh:NodeShape` still gets checked. The spec asks for
   both, so declare both and every SHACL tool agrees.) (The course's tests check this.)
4. **Cooler_1**:

   ```turtle
   burger:CoolerShape a sh:NodeShape ;
       sh:targetClass burger:WalkInCooler ;
       sh:property [ sh:path burger:hasPoint ; sh:minCount 1 ] .
   ```

   (The course's tests check this answer.)

</details>
