# Day 29 — SPARQL: asking Burger Barn questions

**Goal:** write SPARQL `SELECT` queries with patterns, `OPTIONAL`, `ORDER BY` and `GROUP BY`, and read the answers
in Python.

## Read

**SPARQL** is the query language for RDF ([SPARQL 1.1 Query](https://www.w3.org/TR/sparql11-query/)). A query is a
**pattern of triples with blanks** (variables, starting with `?`). The engine finds every way to fill the blanks so
the pattern matches the graph:

```sparql
SELECT ?thing ?label WHERE {
  bb:MainKitchen bb:contains ?thing .     # what does the kitchen contain?
  OPTIONAL { ?thing rdfs:label ?label }   # and its label, if it has one
} ORDER BY ?thing
```

| SPARQL | Means | SQL you already know |
|---|---|---|
| `?thing` | a blank to fill | a column |
| a triple pattern | must match | a join condition |
| `OPTIONAL { ... }` | add it if it's there | `LEFT JOIN` |
| `ORDER BY` | sort | `ORDER BY` |
| `GROUP BY ?room` + `COUNT(?thing)` | count per room | `GROUP BY` + `COUNT` |

[`day29_rdf.py`](day29_rdf.py) asks three questions: what is in the kitchen (with labels), which equipment has a
temperature sensor, and how many things each room contains. The `bb:` and `rdfs:` prefixes come from the Turtle
file, so the queries don't need `PREFIX` lines.

## Run

```bash
uv run python lessons/course.py run 29
```

```
In the kitchen (name, label):
   Fryer_1 'Fryer 1'
   Fryer_2 'Fryer 2'
   Grill_1 'Flat-top grill'
   IceMachine_1 None
   WalkInCooler_1 ''
Equipment with a temperature sensor: [('Fryer_1', 'Fryer_1_OilTemp'), ('Grill_1', 'Grill_1_SurfaceTemp'), ('WalkInCooler_1', 'Cooler_AirTemp')]
Things per room: [('DiningRoom', 1), ('MainKitchen', 5)]
```

`IceMachine_1` comes back with `None`: `OPTIONAL` kept the row even though the label is missing. Without
`OPTIONAL`, the ice machine would vanish from the list, the same way an inner join drops rows.

## How this maps to buildings

> **Buildings box.** "Which equipment has a temperature sensor?" is the first question every FDD tool asks a
> model. On a **Brick** model it is `?equip brick:hasPoint ?p . ?p a brick:Temperature_Sensor`; on **ASHRAE 223P**
> you follow `s223:hasProperty` from equipment to its measured properties; on **Haystack** data you ask for
> points with the `temp sensor` tags and an `equipRef`. Week 7 Day 35 runs today's query, word for word except the
> names, on a tiny Brick building.

## Why it matters

SPARQL is how every question about a model gets asked, by people and by apps such as FDD rules. Once you can read a
pattern, a 20-line query is just 20 small facts that must all be true at once.

## Try it

1. Change the first query to drop the `OPTIONAL`. Which row disappears?
2. Count the points per piece of equipment (`bb:hasPoint`), largest first.
3. **Mini challenge (Burger Barn):** list every temperature sensor with its unit.

<details><summary>Answers</summary>

1. `IceMachine_1`: it has no label, so the required pattern can't match.
2. `SELECT ?equipment (COUNT(?point) AS ?n) WHERE { ?equipment bb:hasPoint ?point } GROUP BY ?equipment ORDER BY DESC(?n)`
   gives one point each for Fryer_1, Grill_1 and WalkInCooler_1. (The cooler's door alarm uses `bb:hasAlarm`; Day 32
   shows how to count it too.)
3. Three sensors, all in `degC`:

   ```sparql
   SELECT ?point ?unit WHERE { ?point a bb:TemperatureSensor ; bb:unit ?unit }
   ```

   (The course's tests check this answer.)

</details>
