# Day 35 — SHACL rules, and the bridge to a real building model

**Goal:** write Burger Barn's rules in SHACL, read a validation report, then run the same kind of rule and the same
Week 6 queries on a tiny building written with Brick names.

## Read

**SHACL**, the Shapes Constraint Language ([W3C SHACL](https://www.w3.org/TR/shacl/)), is the standard way to write
closed-world checks: "every X must have ...". Where OWL (Day 33) assumes missing facts exist somewhere, SHACL
checks what is actually in the graph. The rules are themselves triples, in
[`burger_barn_shapes.ttl`](burger_barn_shapes.ttl). The words you need, all defined in the spec:

| SHACL | Means | Burger Barn |
|---|---|---|
| `sh:NodeShape` | a rule about whole things | `bb:FryerShape` |
| `sh:targetClass` | which things to check (subclasses included) | every `bb:Fryer`; every `bb:Equipment` |
| `sh:property [ sh:path ... ]` | a **property shape**: a rule about one property's values | `bb:oilSetpointC` |
| `sh:minCount` / `sh:maxCount` | at least / at most this many values | exactly one setpoint |
| `sh:datatype` | values must have this datatype | `xsd:decimal`, so `"175"` fails |
| `sh:class` | values must be things of this class | a `bb:TemperatureSensor` |
| `sh:pattern` | text must match this regular expression | serial numbers like `BB-FRY-0001` |
| `sh:minLength` | text at least this long | catches the blank label |
| `sh:severity` | how bad: `sh:Violation` (default), `sh:Warning`, `sh:Info` | missing labels are warnings |
| `sh:message` | what to tell the person | "A fryer needs a temperature point." |
| `sh:in ( ... )` / `sh:hasValue` | the value must be one of this list / exactly this | Day 38's named cook methods |

`sh:targetClass` isn't the only way to pick what to check. A class can *also be* a node shape
(`bb:Fryer a owl:Class, rdfs:Class, sh:NodeShape ; sh:property [ ... ]`), and then SHACL checks every instance of
that class: an *implicit class target*. Brick and ASHRAE 223P ship most of their rules that way. Today's file uses
`sh:targetClass`; Day 39 puts the two side by side and says when to pick each.

**Reading a validation report.** `pyshacl.validate(data, shacl_graph=rules)` returns `conforms` (True only if there
are no results at all, warnings included), plus a **report graph**: one `sh:ValidationResult` per problem, with
`sh:focusNode` (which thing), `sh:resultPath` (which property), `sh:value` (the bad value, if any),
`sh:resultSeverity` and `sh:resultMessage`. Since the report is a graph, you read it with SPARQL, which is what
[`day35_rdf.py`](day35_rdf.py) does.

Then the bridge. [`tiny_building.ttl`](tiny_building.ttl) is a hand-written building with **Brick** names: an AHU
feeding two VAVs, each feeding a zone, with points. It carries a handful of Brick's real `rdfs:subClassOf` facts
(`brick:AHU` → `brick:HVAC_Equipment` → `brick:Equipment`) instead of the whole Brick ontology.
[`tiny_building_shapes.ttl`](tiny_building_shapes.ttl) is the fryer rule with new words: every VAV needs a
temperature point.

| Burger Barn | Tiny building (Brick) |
|---|---|
| `bb:Fryer rdfs:subClassOf bb:CookingEquipment` | `brick:VAV rdfs:subClassOf brick:Terminal_Unit` |
| `bb:hasPoint` / `bb:isPointOf` | `brick:hasPoint` / `brick:isPointOf` |
| `bb:contains+` | `brick:feeds+` (AHU → VAV → zone) |
| "every fryer needs a temperature point" | "every VAV needs a temperature point" |

## Run

```bash
uv run python lessons/course.py run 35
```

```
Restaurant follows its rules: False
   Fryer_2         Violation  A fryer needs a temperature point.
   Fryer_2         Violation  Oil setpoint must be one decimal number.
   Grill_1         Violation  Serial number must look like BB-ABC-1234.
   IceMachine_1    Warning    Missing label.
   WalkInCooler_1  Warning    Blank label.
Building follows its rules: False
   VAV_2           Violation  A VAV needs a temperature point.

Equipment in the building: ['AHU_1', 'VAV_1', 'VAV_2']
Building equipment with a temperature sensor: [('AHU_1', 'AHU_1_SAT'), ('VAV_1', 'VAV_1_ZoneTemp')]
Downstream of AHU_1 (brick:feeds+): ['VAV_1', 'VAV_2', 'Zone_1', 'Zone_2']
```

Five results for the restaurant: Fryer_2's missing point and its text setpoint, the grill's badly formed serial
number, and two warnings for labels. One for the building: VAV_2 has a damper command but no temperature sensor.
The last three lines are Week 6's queries with Brick words: same patterns, new names.

## How this maps to buildings

> **Buildings box.** This *is* buildings. **Brick** is published as an OWL/RDFS ontology **plus** SHACL shapes;
> **ASHRAE 223P** defines most of its rules as SHACL, so a 223P model is "valid" when it passes the standard's
> shapes; and **Haystack 4** defines its tags as defs that export to RDF/Turtle, so the same SPARQL and SHACL tools
> work on Haystack data. OWL isn't "just a web thing": it's how these standards say what an AHU *is*, and SHACL is
> how they check that your model of one is complete.

## Why it matters

An FDD rule is only as good as the model it reads. SHACL turns "the model should have..." into a report you can
run on every model, every time, before any rule trusts it.

## Week 7 further reading

- W3C, [RDF Schema 1.1](https://www.w3.org/TR/rdf-schema/)
- W3C, [OWL 2 Web Ontology Language Primer](https://www.w3.org/TR/owl2-primer/) (sections 4–5: classes, properties)
- W3C, [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) (sections 2 and 4: shapes and core constraints)
- [Brick: relationships](https://docs.brickschema.org/brick/relationships.html), [ASHRAE 223P](https://open223.info/),
  [Project Haystack: RDF](https://project-haystack.org/doc/docHaystack/Rdf)
- [pyshacl](https://github.com/RDFLib/pySHACL), [owlrl](https://github.com/RDFLib/OWL-RL)

## Try it

1. Give `bb:Fryer_2` a temperature point and the setpoint `175.0`. How many results are left?
2. Change `sh:severity sh:Warning` to `sh:Info` on the missing-label rule. Does `conforms` change?
3. **Mini challenge (Burger Barn):** write a shape that says every fryer must have a serial number
   (`sh:minCount 1`). Which fryer breaks it?

<details><summary>Answers</summary>

1. Three: the grill's serial number and the two label warnings.
2. No. Any result, even an `sh:Info`, makes `conforms` False. Read the severities to decide what blocks you.
3. **Fryer_2**:

   ```turtle
   bb:SerialShape a sh:NodeShape ;
       sh:targetClass bb:Fryer ;
       sh:property [ sh:path bb:serialNumber ; sh:minCount 1 ;
                     sh:message "A fryer needs a serial number." ] .
   ```

   (The course's tests check this answer.)

</details>
