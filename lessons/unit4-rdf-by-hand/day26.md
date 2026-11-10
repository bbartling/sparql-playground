# Day 26 — Your first triples: Burger Barn, written by hand

**Goal:** write down facts about a (made-up) burger restaurant as **triples**, load them with rdflib, and find the
typo a computer can't see.

## Read

Weeks 1–5 started from data someone else made: CSV exports and a ready-made model. This week and next you write the
model yourself, by hand, about something everybody understands: a burger restaurant called **Burger Barn** (made
up, like its menu).

This is how university Semantic Web courses start too: the **RDF data model** first (the W3C
[RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/) is the standard introduction), then vocabularies on top of
it. RDF stores facts as **triples**. Every triple is one short sentence with three parts:

| subject (the thing) | predicate (the relationship) | object (the other thing) |
|---|---|---|
| Burger Barn | contains | Kitchen |
| Kitchen | contains | Fryer_1 |
| Fryer_1 | hasPoint | Fryer_1_OilTemp |

That last row should look familiar. A restaurant contains a kitchen, a kitchen contains a fryer, and the fryer has
a temperature **point**. A building contains an AHU, and the AHU has points. Same shape, smaller and tastier.

Open [`day26_first_triples.ttl`](day26_first_triples.ttl). It is **Turtle**, the most readable way to write
triples. One line per triple, a dot at the end, `#` for comments. Every name is a full web address (an **IRI**) in
angle brackets, like `<https://example.org/burger-barn#Fryer_1>`. It doesn't have to exist on the web. It's
just a name that nobody else will use by accident. (Yes, it's long. Tomorrow's prefixes fix that.)

[`day26_rdf.py`](day26_rdf.py) does three things:

| Step | What it does | rdflib |
|---|---|---|
| 1. load | read the file into a graph | `g = Graph(); g.parse("...ttl")` |
| 2. look | print every triple, short names only | `for s, p, o in g:` and `.fragment` (the part after `#`) |
| 3. count | how often each predicate is used | a plain `dict` |
| 4. ask | what does the kitchen contain? | `g.objects(kitchen, contains)` |

## Run

```bash
uv run python lessons/course.py run 26
```

```
The graph has 6 triples:
  BurgerBarn contains Kitchen
  Fryer_1 hasPoint Fryer_1_OilTemp
  Kitchen contains Fryer_1
  Kitchen contains WalkInCooler
  Kitchen contians Grill
  WalkInCooler hasPoint Cooler_AirTemp

How often each predicate is used:
  contains 3
  contians 1
  hasPoint 2

The kitchen contains: Fryer_1, WalkInCooler
```

Count the predicates: `contains` 3 times, `hasPoint` twice, and `contians` once. That's the typo. To RDF,
`contians` is a perfectly good, brand-new relationship, so there's **no error**. The grill just quietly disappears
from "what does the kitchen contain?". A typo in a column name crashes your SQL; a typo in RDF makes a new word.
Counting predicates (and, from Week 7, checking them against a list of known words) is how you catch it.

## How this maps to buildings

> **Buildings box.** Swap the words and this file is a building model: `Building_1 contains AHU_1`,
> `AHU_1 hasPoint AHU_1_SAT`. **Brick** (the open building ontology) says exactly that with `brick:hasPoint`;
> **ASHRAE 223P** writes its models as the same kind of triples; and **Project Haystack** tags (`equip`, `ahu`,
> `equipRef`) can be exported as triples too (Week 5's `model/building_50.ttl` is one). A misspelled
> `brick:hasPiont` fails the same silent way, which is why real models get checked (Week 7).

## Why it matters

Everything else in Weeks 6–7 is built from this one idea: small three-part facts, written by hand, that a program
can read. Once facts are triples, any question about them is a pattern over triples.

## Try it

1. Add a triple saying the kitchen contains an ice machine (`#IceMachine`). How many triples now?
2. Which pieces of equipment have a temperature point? Answer from the printed triples, no code.
3. **Mini challenge (Burger Barn):** fix the typo in your copy of the file. How many things does the kitchen
   contain now?

<details><summary>Answers</summary>

1. 7. One new line:
   `<https://example.org/burger-barn#Kitchen> <https://example.org/burger-barn#contains> <https://example.org/burger-barn#IceMachine> .`
2. `Fryer_1` (`Fryer_1_OilTemp`) and `WalkInCooler` (`Cooler_AirTemp`). The grill has none.
3. **3:** Fryer_1, WalkInCooler and Grill. Change `contians` to `contains` and the grill comes back.
   (The course's tests check this answer.)

</details>
