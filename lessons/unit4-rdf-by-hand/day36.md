# Day 36 — Ontology Development 101: scope, competency questions and reuse

**Goal:** start a new ontology the way the textbook method does: decide what it's for, write the questions it
must answer, look for terms that already exist, and list the terms you still need.

## Read

Weeks 6–7 grew Burger Barn's ontology one idea at a time. This week you build one *on purpose*, following the
classic beginner's method, Noy and McGuinness's
[Ontology Development 101](https://protege.stanford.edu/publications/ontology_development/ontology101.pdf). Simplified,
it has eight steps:

| Step | What you do | This week |
|---|---|---|
| 1 | Set the **scope** and write **competency questions** | today |
| 2 | Look for existing ontologies to **reuse** | today (and Day 40) |
| 3 | **List the terms** you need | today |
| 4 | Define the **classes** and their hierarchy | Day 37 |
| 5 | Define the **properties** | Day 37 |
| 6 | Add **restrictions** | Day 38 |
| 7 | Create **instances** | Day 38 |
| 8 | **Test**: answer the competency questions with SPARQL, validate with SHACL | Day 39 |

**Competency questions** are the heart of it: plain-English questions the finished ontology must be able to
answer, such as "which menu items depend on a fryer?". They keep the ontology small (no question, no term) and
they become its tests on Day 39.

**Scope** says just as clearly what is *out*: staff, prices and recipes are real, but no question needs them.

**Reuse** means: before inventing `Equipment`, check whether a standard already has it. Here we look in the few
Brick terms in `tiny_building.ttl`. (The real Brick has about a thousand classes, and you'd also check ASHRAE
223P, Haystack, QUDT for units and SKOS for definitions.) [`day36_rdf.py`](day36_rdf.py) writes the scope and five
competency questions, lists every term they mention, and looks for a Brick term with the same name.

## Run

```bash
uv run python lessons/course.py run 36
```

```
Scope: Burger restaurant equipment, its sensor points, and which menu items need it.
Out of scope: staff and shifts, prices and sales, recipes and cooking steps

Competency questions:
   CQ1 Which menu items depend on a fryer? -> MenuItem, Fryer, cookedOn, hasIngredient
   CQ2 Which equipment has no temperature sensor? -> Equipment, hasPoint, TemperatureSensor
   CQ3 Where is each piece of equipment? -> Equipment, hasLocation, Kitchen
   CQ4 What oil temperature is each fryer set to? -> Fryer, oilSetpoint
   CQ5 How many calories is each menu item? -> MenuItem, hasCalories

Terms needed (11), and a Brick term with the same name:
   Equipment          brick:Equipment
   Fryer              (none: a new burger: term)
   Kitchen            (none: a new burger: term)
   MenuItem           (none: a new burger: term)
   TemperatureSensor  brick:Temperature_Sensor
   cookedOn           (none: a new burger: term)
   hasCalories        (none: a new burger: term)
   hasIngredient      (none: a new burger: term)
   hasLocation        brick:hasLocation
   hasPoint           brick:hasPoint
   oilSetpoint        (none: a new burger: term)
```

Four of the eleven terms already exist in Brick. The other seven (`Fryer`, `MenuItem`, `oilSetpoint`, ...) are
restaurant words, and Brick, rightly, has no idea what a fryer is. So the burger ontology gets its own namespace
(`burger:`) for all eleven, and on Day 40 we say how the four overlap with Brick. This is exactly the pattern Brick
recommends for extensions.

## How this maps to buildings

> **Buildings box.** For an FDD project, the competency questions are the rule inputs: "which AHUs have a supply
> air temperature sensor and a fan status?", "which VAVs does AHU_1 feed?". Write them first, and you know which
> **Brick** classes, **ASHRAE 223P** connections or **Haystack** tags your model must have, and you can test the
> model against them before any rule runs.

## Why it matters

Most ontology projects that fail try to model everything. Competency questions keep you to what someone needs,
and give you a test for "done".

## Week 8 further reading

- N. F. Noy and D. L. McGuinness, [Ontology Development 101: A Guide to Creating Your First Ontology](https://protege.stanford.edu/publications/ontology_development/ontology101.pdf)
  (Stanford, 2001). The method this week follows.
- METHONTOLOGY (Fernández-López, Gómez-Pérez and Juristo, 1997): a more formal, life-cycle method for building
  ontologies like software.
- The NeOn methodology (Suárez-Figueroa, Gómez-Pérez and others, around 2012): scenarios for building ontologies
  by reusing and re-engineering existing ones.
- W3C, [OWL 2 Primer](https://www.w3.org/TR/owl2-primer/), [SHACL](https://www.w3.org/TR/shacl/),
  [SPARQL 1.1 Query](https://www.w3.org/TR/sparql11-query/)
- [Brick: extending Brick](https://docs.brickschema.org/extra/extending.html)

## Try it

1. Add a sixth competency question: "Which equipment is in the kitchen?" Which new terms does it need?
2. Move "prices" into scope. Write a competency question for it and list its terms.
3. **Mini challenge (Burger Barn):** write a competency question for "which fryer cooks the onion rings?", then
   answer it with SPARQL on `burger.ttl` + `burger_site.ttl`.

<details><summary>Answers</summary>

1. None: `Equipment`, `hasLocation` and `Kitchen` are already on the list. A good sign.
2. For example "What does each menu item cost?" needs `MenuItem` (have it) and a new `price` property, plus a
   decision about currency (QUDT or a plain `xsd:decimal` in one currency).
3. **Fryer_2**: `SELECT ?fryer WHERE { site:OnionRings burger:cookedOn ?fryer }`. (The course's tests check this
   answer.)

</details>
