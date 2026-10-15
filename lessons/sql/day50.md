# Day 50 — Read the small amount of RDF your SQL workflow needs

[Previous: Day 49](day49.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 51](day51.md)

**Week 8 · 45–75 minutes.** Prerequisites: Days 1–49, or equivalent SQL skills.

## Goal

Recognize triples, IRIs, prefixes and literals in the course metadata graph.

## Before you start

Open `lessons/sql/model.ttl` in an editor. It is a small synthetic instance graph, separate from stored samples. Run `uv run python lessons/sql/graph_lab.py --check` from the repository root; this checks fixture bindings offline rather than querying a running database.

## Concept

An RDF triple has subject, predicate and object. The subject and predicate are identifiers; the object may be another identifier or a literal value. An IRI identifies a thing or relationship. A prefix abbreviates an IRI: `brick:` expands to `https://brickschema.org/schema/Brick#`. Prefix spelling is local shorthand, not identity.

Turtle's `a` abbreviates `rdf:type`. A quoted label such as `"Supply A"` is a literal, not an equipment identifier. The two sites deliberately share that equipment label. Course IRIs use `https://example.org/course#`; their UUID-bearing suffixes are opaque. Do not split suffixes to recover database keys. Follow explicit reference properties instead.

The graph describes which point means what and where its history is referenced. It does not contain the temperature and pressure observations from the SQL sample table. This week teaches practical discovery; you do not need to author a new ontology.

## Tiny example

```sparql
SELECT ?subject ?predicate ?object
WHERE { ?subject ?predicate ?object }
LIMIT 6
```

Run the supplied equivalent with `uv run python lessons/sql/graph_lab.py lessons/sql/sparql/day50_triples.rq`. JSON bindings preserve RDF term kinds such as `uri`, `literal` and `bnode`. A blank-node identifier is local to that graph serialization, not a permanent timeseries key.

## SQL challenge

Choose one equipment and one point from the Turtle file. Write a short mapping between their RDF facts and columns in `course.equipment` and `course.point`. Verify identities through explicit metadata fields, distinguishing a label literal from an IRI and a reference node from a stored sample.

## Experiment

Copy the tiny query into your own file and rename a prefix while keeping its expanded namespace unchanged. Predict whether results change. Then change the namespace itself and explain why matching differs.

## Acceptance checks

- The offline check verifies 42 point bindings.
- You can label subject, predicate and object in three actual triples.
- You distinguish an IRI, literal and blank node in JSON.
- No history is claimed to have been read merely because metadata was returned.

## Stretch and reflection

Which metadata could an application cache, and what change would require invalidating that cache? Save the question for the revision discussion on Day 55.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day50/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-8) for exact language and domain details.

[Previous: Day 49](day49.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 51](day51.md)
