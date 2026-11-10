# Day 33 — OWL classes: owl:Thing, disjointness, restrictions and the open world

**Goal:** see what OWL says about classes (everything is an `owl:Thing`, some classes can't overlap, a class can
require something), and why OWL can't catch a missing value while SHACL can.

## Read

Day 31 built the class tree with RDFS. OWL adds a few more class words. These are the ones you'll meet in building
ontologies:

| OWL | Means | Burger Barn |
|---|---|---|
| `owl:Thing` | the top class: everything is one | `bb:Equipment rdfs:subClassOf owl:Thing` |
| `owl:Class` | "this is a class" (an OWL tool's way of saying it) | `bb:Fryer a owl:Class` |
| `owl:disjointWith` | nothing can be in both classes | cooking equipment vs refrigeration, burger vs drink |
| `owl:Restriction` + `owl:someValuesFrom` | every member has *some* value of this kind | every fryer has some temperature point |

A **restriction** is an unnamed class, written `[ ... ]` in Turtle. In `burger_barn_ontology.ttl`:

```turtle
bb:Fryer rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty bb:hasPoint ;
    owl:someValuesFrom bb:TemperatureSensor
] .
```

Read it as "every fryer is one of the things that have some temperature point". (`owl:cardinality`,
`owl:minCardinality` and `owl:allValuesFrom` are its cousins, met in Week 8.)

Now the idea that surprises everyone: the **open-world assumption**. OWL assumes your data is *incomplete*: what
isn't written down might still be true. Fryer_2 has no temperature point in the data. Does OWL complain? No. It
concludes "Fryer_2 has a temperature point we don't know about yet". **No missing value is ever an error to OWL.**
What OWL *can* catch is a contradiction: something typed with two disjoint classes can't exist in any world.

SHACL (Day 35) works the other way, **closed world**: what isn't in the graph isn't there. That's why building
ontologies pair them: OWL/RDFS to say what terms mean, SHACL to check that a model is complete.

[`day33_rdf.py`](day33_rdf.py) runs the OWL reasoner on the real data, then on a copy with one deliberate mistake
(the ice machine typed as a grill too), then SHACL on the real data.

## Run

```bash
uv run python lessons/course.py run 33
```

```
Triples: before inference 193 | after 669
Fryer_1 is a: ['CookingEquipment', 'Equipment', 'Fryer', 'Thing']
Things that are an owl:Thing after inference: 14

OWL problems in the real data: [] <- open world: nothing missing to OWL
OWL problems after typing IceMachine_1 as a Grill too:
   Disjoint classes bb:CookingEquipment and bb:Refrigeration have a common individual bb:IceMachine_1
SHACL problems with Fryer_2 (closed world): ['A fryer needs a temperature point.', 'Oil setpoint must be one decimal number.']
```

Three results, one lesson. After inference Fryer_1 is a Fryer, CookingEquipment, Equipment **and** owl:Thing. The
real data gives OWL nothing to complain about, even with Fryer_2's missing point. The ice machine typed as a grill
breaks `owl:disjointWith`, and owlrl reports it. SHACL, checking only what is written, finds Fryer_2's missing point
(and its text setpoint).

## How this maps to buildings

> **Buildings box.** **Brick** keeps `brick:Point`, `brick:Equipment` and `brick:Location` as separate
> top-level classes: a sensor is never an AHU. Declare classes like these disjoint (as Burger Barn does) and
> "I typed a sensor as an AHU" becomes a contradiction a reasoner catches. **Brick**
> and **ASHRAE 223P** then ship **SHACL shapes** for the closed-world checks ("a VAV must have a temperature
> point"), because OWL can't. That is why 223P leans so heavily on SHACL. **Haystack** has no reasoner: its
> tooling checks tags directly, which is closed-world too.

## Why it matters

"The reasoner found no problems" does not mean "the model is complete". For FDD you need both: meanings you can
reason with, and checks that the points your rules need are really there.

## Try it

1. Add `bb:Cola a bb:Burger` to the menu file. Which disjointness does it break?
2. Would OWL complain if a menu item had **no** calorie number? Why not?
3. **Mini challenge (Burger Barn):** write a SPARQL query, no reasoner, that finds anything typed with two
   disjoint classes. Test it with the ice machine typed as a grill.

<details><summary>Answers</summary>

1. `bb:Burger owl:disjointWith bb:Drink`: Cola is already a `bb:Drink`.
2. No. Open world: OWL assumes the number exists but isn't written down. Only a closed-world check (a query or a
   SHACL `sh:minCount 1`) can say it's missing.
3. It returns `IceMachine_1, CookingEquipment, Refrigeration`:

   ```sparql
   SELECT ?thing ?class1 ?class2 WHERE {
     ?class1 owl:disjointWith ?class2 .
     ?thing a/rdfs:subClassOf* ?class1 .
     ?thing a/rdfs:subClassOf* ?class2 .
   }
   ```

   (The course's tests check this answer.)

</details>
