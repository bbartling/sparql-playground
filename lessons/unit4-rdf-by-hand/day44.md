# Day 44 — A CI check for your ontology: SHACL plus a "doctor" query

**Goal:** write the check a CI job would run on every pull request: load the ontology and some synthetic test data,
run the SHACL rules, and sort every term the data uses into standard, custom, deprecated and unknown.

## Read

**CI** (continuous integration) means a script runs automatically on every change, for example a GitHub Actions job
on every pull request, and a red result blocks the merge. For an ontology repo the job loads:

- the ontology ([`burger.ttl`](burger.ttl)) and its shapes ([`burger_shapes.ttl`](burger_shapes.ttl)),
- **synthetic test data**: a small made-up file written to exercise the rules,
  [`burger_ci_data.ttl`](burger_ci_data.ttl). This one has planted mistakes.

and runs two checks:

1. **SHACL** (Day 35): does the data follow the rules?
2. **The doctor**: is every class and property the data uses actually defined somewhere? Day 26's lesson: a typo
   in RDF is not an error, it's a new word. The doctor sorts every term into:

| Kind | Rule | Verdict |
|---|---|---|
| standard | its namespace is a known standard (RDF, RDFS, OWL, XSD, SKOS, Dublin Core, Brick) | fine |
| custom | defined in our ontology | fine |
| deprecated | defined, but `owl:deprecated true` | fail (migrate it, Day 43) |
| unknown | none of the above | **fail**: almost always a typo |

[`day44_rdf.py`](day44_rdf.py) does both and prints PASS or FAIL. As a GitHub Actions step it's one line,
`uv run python lessons/unit4-rdf-by-hand/day44_rdf.py`, plus a final `sys.exit(0 if ci_passes else 1)` so a FAIL
turns the job red.

## Run

```bash
uv run python lessons/course.py run 44
```

```
standard   (3): ['type', 'label', 'Temperature_Sensor']
custom     (7): ['Fryer', 'Grill', 'Kitchen', 'TemperatureSensor', 'hasLocation', 'hasPoint', 'oilSetpoint']
deprecated (1): ['Cooler']
unknown    (2): ['https://example.org/burger#Fryr', 'https://example.org/burger#hasPiont']

SHACL violations: [('Fryer_1', 'A fryer needs a temperature point.')]

CI result: FAIL
```

The doctor catches both typos (`Fryr`, `hasPiont`) and the deprecated `Cooler`. SHACL catches Fryer_1, whose point
is linked with the misspelled property, so as far as the rules can see it has no point. The Brick class
`brick:Temperature_Sensor` counts as standard. (A stricter doctor would also load Brick itself and check that the
term exists there.)

## How this maps to buildings

> **Buildings box.** Run the same job on a site's model before FDD rules use it: the **Brick** and **ASHRAE 223P**
> SHACL shapes plus your project's own, and a doctor query that flags misspelled Brick classes
> (`brick:Supply_Air_Temp_Sensor` instead of `brick:Supply_Air_Temperature_Sensor`) or unknown **Haystack** tags.
> A misspelled class means a point the rules will never find, so failing the build is the right answer.

## Why it matters

Ontology mistakes are silent. A CI check makes them loud, and makes them loud *before* anyone publishes data or
trusts a rule that depends on it.

## Try it

1. Add `brick:Temperature_Senser` (misspelled) to the test data. Which list is it in? Why is that a weakness?
2. Why use made-up test data instead of a real restaurant's file?
3. **Mini challenge (Burger Barn):** fix the two typos and the deprecated class in a copy of the CI data. Does CI
   pass now?

<details><summary>Answers</summary>

1. "standard", because only its namespace is checked. Loading the real Brick ontology and checking that the term is
   defined there would catch it.
2. You choose exactly which mistakes it contains, so the test checks that each one is caught. It's small, it never
   changes under you, and it holds no real site's data.
3. **No.** Fixing `Fryr` turns Fryer_2 into a real `burger:Fryer`, and now the fryer rule sees it has no point, no
   setpoint and no location. Fixing one bug can expose the next; that's CI doing its job. (The course's tests check
   this answer.)

</details>
