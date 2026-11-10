# Day 27 — Prefixes, `a` (rdf:type) and labels

**Goal:** write Turtle the short way with **prefixes**, say what kind of thing each thing is with `a`, and give
things human-readable **labels**, then spot the missing and blank ones.

## Read

Open [`burger_barn.ttl`](burger_barn.ttl), the restaurant you'll use for the rest of the two weeks. Three new
pieces of Turtle make it much shorter than yesterday's file:

| Turtle | Means | Example |
|---|---|---|
| `@prefix bb: <https://example.org/burger-barn#> .` | `bb:` is short for that long address | `bb:Fryer_1` |
| `a` | short for `rdf:type`: "is a kind of" | `bb:Fryer_1 a bb:Fryer` |
| `;` | same subject, next predicate | `bb:Fryer_1 a bb:Fryer ; rdfs:label "Fryer 1" .` |
| `,` | same subject and predicate, next object | `bb:contains bb:Fryer_1, bb:Fryer_2` |

`rdfs:label` is the standard predicate for a human-readable name. `bb:Fryer_1` is the **name a program uses**;
`"Fryer 1"` is the **label a person reads**. Labels are values (strings), not things.

Things in a triple come in two flavours:

- a **URI** (an IRI): a thing with a name, like `bb:Fryer` or `bb:Fryer_1_OilTemp`. It can be the subject of
  more triples.
- a **literal**: a plain value, like `"Fryer 1"` or `175`. A literal is always an object, never a subject.

[`day27_rdf.py`](day27_rdf.py) lists every typed thing with its label (`g.value(thing, RDFS.label)`, which
returns `None` when there is none), shows Fryer_1's own triples marked URI or literal, and counts things per type.

## Run

```bash
uv run python lessons/course.py run 27
```

```
The graph has 59 triples and 14 typed things:
  BurgerBarn           a Restaurant         label: 'Burger Barn'
  Cooler_AirTemp       a TemperatureSensor  label: 'Walk-in cooler air temperature'
  Cooler_DoorAlarm     a DoorAlarm          label: 'Walk-in cooler door left open'
  DiningRoom           a DiningRoom         label: 'Dining room'
  Fryer_1              a Fryer              label: 'Fryer 1'
  Fryer_1_OilTemp      a TemperatureSensor  label: 'Fryer 1 oil temperature'
  Fryer_2              a Fryer              label: 'Fryer 2'
  Grill_1              a Grill              label: 'Flat-top grill'
  Grill_1_SurfaceTemp  a TemperatureSensor  label: 'Grill surface temperature'
  IceMachine_1         a IceMachine         label: None
  MainKitchen          a Kitchen            label: 'Main kitchen'
  NorthRegion          a FranchiseRegion    label: 'North region'
  SodaFountain_1       a SodaFountain       label: 'Soda fountain'
  WalkInCooler_1       a WalkInCooler       label: ''

Fryer_1's triples:
  type           Fryer                (URI)
  label          Fryer 1              (literal)
  fryTime        PT3M                 (literal)
  hasPoint       Fryer_1_OilTemp      (URI)
  lastInspected  2026-10-01T09:30:00  (literal)
  oilSetpointC   175.0                (literal)
  serialNumber   BB-FRY-0001          (literal)

Things per type: {'DiningRoom': 1, 'DoorAlarm': 1, 'FranchiseRegion': 1, 'Fryer': 2, 'Grill': 1, 'IceMachine': 1, 'Kitchen': 1, 'Restaurant': 1, 'SodaFountain': 1, 'TemperatureSensor': 3, 'WalkInCooler': 1}
```

Two labels are wrong in two different ways. `IceMachine_1` has **no** label triple at all (`None`).
`WalkInCooler_1` has one, but it's **blank** (`''`). A query for "things without a label" finds only the first; a
person reading a dashboard gets an empty cell for the second. Day 30 finds both with SPARQL, and Day 35 writes a
rule for each.

## How this maps to buildings

> **Buildings box.** `ex:AHU_1 a brick:AHU ; rdfs:label "AHU 1"` is exactly how a **Brick** model types and names
> equipment, with the `brick:` prefix standing for `https://brickschema.org/schema/Brick#`. **ASHRAE 223P** uses
> the prefix `s223:` the same way. **Haystack** writes the type as marker tags (`equip`, `ahu`) and the label as
> `dis:"AHU 1"`. A missing or blank label is the classic "why does this point show up as a long ID on my
> graphics?" bug.

## Why it matters

Types are how you ask for "every fryer" instead of naming each one, and labels are what people see. Get both into
the habit of every model you write, and check for the missing and blank ones.

## Try it

1. How many things are typed `bb:Fryer`? Which line of the output tells you?
2. In `burger_barn.ttl`, give the ice machine the label `"Ice machine"`. What changes in the output?
3. **Mini challenge (Burger Barn):** write a SPARQL query (or a Python loop) that lists every temperature sensor.
   How many does Burger Barn have?

<details><summary>Answers</summary>

1. 2 (`'Fryer': 2` in "Things per type").
2. Its line shows `label: 'Ice machine'`, and the graph has one more triple (60).
3. **3:** `Cooler_AirTemp`, `Fryer_1_OilTemp` and `Grill_1_SurfaceTemp`.

   ```python
   for row in g.query("SELECT ?sensor WHERE { ?sensor a bb:TemperatureSensor }"):
       print(row.sensor.fragment)
   ```

   (The `bb:` prefix comes from the Turtle file, so the query doesn't need a PREFIX line.)

</details>
