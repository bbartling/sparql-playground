# Day 43 — Keeping an ontology in a repo: versions, deprecation and migration

**Goal:** give the ontology a version, retire a term without breaking anyone, and move old data onto the new term
with one SPARQL update.

## Read

A published ontology lives in a **git repository** like any code. A sensible layout:

```
burger-ontology/
├── burger.ttl              the ontology (TBox): terms, labels, definitions
├── burger_shapes.ttl       SHACL rules, separate (Day 39)
├── burger_alignment.ttl    links to Brick, separate (Day 40)
├── examples/               small example data files (ABox)
├── tests/                  the CI check (Day 44)
└── CHANGELOG.md            what changed in each release, and how to migrate
```

**Versions.** The ontology describes itself (top of [`burger.ttl`](burger.ttl)):

| Triple | Means |
|---|---|
| `owl:versionInfo "1.1.0"` | the version number, for people |
| `owl:versionIRI <https://example.org/burger/1.1.0>` | an IRI for *this exact release* |
| `owl:priorVersion <https://example.org/burger/1.0.0>` | the one before |

The **term** IRIs (`burger:Fryer`) never contain a version: only the ontology's version IRI does. A common rule for
the number (semantic versioning): **patch** (1.1.**1**) fixes a typo in a definition; **minor** (1.**2**.0) adds
terms; **major** (**2**.0.0) changes what an existing term means, which you should almost never do.

**Deprecation instead of deletion.** Version 1.0.0 called the walk-in cooler `burger:Cooler`. In 1.1.0 it's
`burger:WalkInCooler`. Deleting `Cooler` would silently break every file that uses it, so instead:

```turtle
burger:Cooler a owl:Class ;
    owl:deprecated true ;
    dcterms:isReplacedBy burger:WalkInCooler ;
    skos:definition "Old name for a walk-in cooler. Use burger:WalkInCooler (since 1.1.0)." .
```

**Migration notes** tell users what to change, and the best migration note is a script.
[`day43_rdf.py`](day43_rdf.py) reads the version, lists deprecated terms, and migrates an old 1.0.0 data file,
[`burger_site_v1.ttl`](burger_site_v1.ttl), with a SPARQL **update**, which changes the graph instead of just
reading it:

```sparql
DELETE { ?thing a ?old }
INSERT { ?thing a ?new }
WHERE  { ?thing a ?old . ?old owl:deprecated true ; dcterms:isReplacedBy ?new }
```

Because it reads the replacement from the ontology, the same update will handle every future deprecation too. (It
changes only the copy in memory; the file on disk is untouched.)

## Run

```bash
uv run python lessons/course.py run 43
```

```
Version 1.1.0 (https://example.org/burger/1.1.0), previous: https://example.org/burger/1.0.0. Version IRI matches: True
Deprecated -> replacement: {'Cooler': 'WalkInCooler'}

Old data using deprecated classes, before migration: [('Cooler_A', 'Cooler'), ('Cooler_B', 'Cooler')]
...after migration: []
Walk-in coolers after migration: ['Cooler_A', 'Cooler_B']
```

## How this maps to buildings

> **Buildings box.** **Brick** marks retired classes with `owl:deprecated` and a pointer to the replacement
> rather than deleting them, so tools can update older models. **ASHRAE 223P** and **Haystack** publish versioned
> releases too. A site model with years of FDD results attached is exactly the "old data file" you must migrate,
> never break.

## Why it matters

Ontologies outlive their first version. Versions, deprecation and a migration script let you improve the terms
without breaking anyone's data.

## Try it

1. Is adding `burger:IceMachine` a patch, minor or major change?
2. Deprecate `burger:oilSetpoint` in favour of a new `burger:oilSetpointC`. What must the update query match?
3. **Mini challenge (Burger Barn):** release 1.2.0. Which three lines in the ontology header change, and to what?

<details><summary>Answers</summary>

1. Minor: new terms, nothing existing changes meaning.
2. Properties, not types: `DELETE { ?s ?old ?v } INSERT { ?s ?new ?v } WHERE { ?s ?old ?v . ?old owl:deprecated true ; dcterms:isReplacedBy ?new }`.
3. `owl:versionInfo "1.2.0"`, `owl:versionIRI <https://example.org/burger/1.2.0>` and
   `owl:priorVersion <https://example.org/burger/1.1.0>`. (The course's tests check this answer.)

</details>
