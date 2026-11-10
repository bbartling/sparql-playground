# Day 31 — RDFS: classes, hierarchies, domain, range and entailment

**Goal:** build Burger Barn's class hierarchy with RDF Schema, find "all equipment" two ways, and see what an
RDFS reasoner adds from `rdfs:domain` and `rdfs:range`.

## Read

Week 6 used words like `bb:Fryer` and `bb:hasPoint` without saying what they mean. This week you write that down:
your own **ontology**, in [`burger_barn_ontology.ttl`](burger_barn_ontology.ttl). University courses teach it in
layers, and so does this week: **RDFS** today, **OWL** on Days 32–33, **SHACL** on Day 35.

Two words you will see in papers and tools: the **TBox** ("terminology box") is the ontology, the *kinds* of
things and properties; the **ABox** ("assertion box") is the facts about particular things. Here the TBox is
`burger_barn_ontology.ttl` and the ABox is `burger_barn.ttl`. That's all the two words mean.

**RDF Schema** ([RDFS 1.1](https://www.w3.org/TR/rdf-schema/)) gives you four words that do most of the work:

| RDFS | Means | Burger Barn |
|---|---|---|
| `rdfs:Class` / `owl:Class` | "this name is a kind of thing" | `bb:Fryer a owl:Class` |
| `rdfs:subClassOf` | "every X is also a Y" | `bb:Fryer rdfs:subClassOf bb:CookingEquipment` |
| `rdfs:domain` | "whatever has this property is a ..." | `bb:hasPoint rdfs:domain bb:Equipment` |
| `rdfs:range` | "whatever this property points at is a ..." | `bb:hasPoint rdfs:range bb:Point` |

(The file says `owl:Class` rather than `rdfs:Class`. For today they mean the same; OWL tools prefer `owl:Class`.)
At the very top sits `owl:Thing`: every class is a kind of Thing.

Now the important idea: **entailment**. The rules of RDFS say which extra triples *follow* from the ones you wrote.
If `Fryer_1 a Fryer` and `Fryer subClassOf CookingEquipment`, then `Fryer_1 a CookingEquipment` follows, even
though nobody wrote it. You can get those answers two ways: a **property path** in the query
(`a/rdfs:subClassOf*`: "a type, then up the tree any number of steps"), or a **reasoner** that adds the entailed
triples to the graph. [`day31_rdf.py`](day31_rdf.py) does both, using `owlrl` with RDFS rules.

## Run

```bash
uv run python lessons/course.py run 31
```

```
TBox (ontology) 134 triples, ABox (facts) 59 triples

Class tree (class -> parent):
   Burger -> MenuItem
   CookingEquipment -> Equipment
   DiningRoom -> Place
   DoorAlarm -> Point
   Drink -> MenuItem
   Equipment -> Thing
   FranchiseRegion -> Place
   Fryer -> CookingEquipment
   Grill -> CookingEquipment
   IceMachine -> Refrigeration
   Ingredient -> Thing
   Kitchen -> Place
   MenuItem -> Thing
   Place -> Thing
   Point -> Thing
   Refrigeration -> Equipment
   Restaurant -> Place
   SodaFountain -> Equipment
   TemperatureSensor -> Point
   WalkInCooler -> Refrigeration

From Fryer up: Fryer -> CookingEquipment -> Equipment -> Thing
?thing a bb:Equipment:                 []
?thing a/rdfs:subClassOf* bb:Equipment: ['Fryer_1', 'Fryer_2', 'Grill_1', 'IceMachine_1', 'SodaFountain_1', 'WalkInCooler_1']

RDFS entailment: triples 194 -> 449
Types given to the untyped mixer and its point: [('Mixer_1', 'Equipment'), ('Mixer_1_Speed', 'Point')]
```

`?thing a bb:Equipment` finds nothing: no triple says exactly that. The path finds all six. Then the surprise: a
brand-new mixer, written with **no type at all**, only `bb:Mixer_1 bb:hasPoint bb:Mixer_1_Speed`, comes out of
the reasoner typed `Equipment`, and its point typed `Point`. That's domain and range at work. They are **not
checks**: RDFS never says "error, that isn't equipment". It concludes "then it must be equipment". If you want a
check, that's SHACL (Day 35).

## How this maps to buildings

> **Buildings box.** **Brick** is built exactly like this: `brick:AHU rdfs:subClassOf brick:HVAC_Equipment`,
> which is a subclass of `brick:Equipment`. So `?x a/rdfs:subClassOf* brick:Equipment` finds AHUs, VAVs and
> pumps in one query. **ASHRAE 223P** has its own class tree (`s223:Equipment`, `s223:Sensor`, ...), and
> **Haystack 4** defines its tags with "is" relationships (`ahu` is an `equip`) that export to RDF as
> `rdfs:subClassOf`. And watch domain and range in real models: a mistyped `brick:hasPoint` on a room makes a
> reasoner call the room "equipment".

## Why it matters

A class tree turns "every fryer, grill, cooler and ice machine" into one word, `Equipment`. Entailment is how a
query for that word finds them all, whether you write the path or let a reasoner add the triples.

## Try it

1. Add `bb:Toaster` as a kind of `bb:CookingEquipment` and a `bb:Toaster_1` in the facts. Does it show up in the
   path query? In the plain one?
2. What does the reasoner conclude if you write `bb:Kitchen_2 bb:hasPoint bb:Kitchen_2_Temp`?
3. **Mini challenge (Burger Barn):** add `bb:Shake_1 bb:hasCalories 600` with no type, then run the RDFS
   reasoner. What is the shake now?

<details><summary>Answers</summary>

1. The path query, yes. The plain query, no (until you run the reasoner).
2. That `Kitchen_2` is `Equipment`, because `bb:hasPoint` has domain `bb:Equipment`. Probably not what you meant:
   domain and range infer, they don't check.
3. **A `bb:MenuItem`**, because `bb:hasCalories` has domain `bb:MenuItem`. (The course's tests check this answer.)

</details>
