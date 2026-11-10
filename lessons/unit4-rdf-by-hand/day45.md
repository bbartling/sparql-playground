# Day 45 — The release checklist, and what comes next

**Goal:** run every Week 8–9 check on the real files in one script, and decide whether version 1.1.0 is ready to
publish.

## Read

Before a release, you want one command that says yes or no. [`day45_rdf.py`](day45_rdf.py) combines everything
from the last two weeks:

| Check | From |
|---|---|
| every term has a label and a definition | Day 37 |
| the version IRI matches the version number, and a prior version is recorded | Day 43 |
| the alignment and the example data use no unknown `burger:` terms | Days 40 and 44 |
| the example data passes the SHACL shapes | Day 39 |
| a competency question still gets an answer | Days 36 and 39 |

If every line says `ok`, you'd tag the release in git, publish `burger.ttl` (plus the shapes, the alignment and an
HTML page) where your persistent IRI points (Day 42), and add a CHANGELOG entry with the migration notes (Day 43).

## Run

```bash
uv run python lessons/course.py run 45
```

```
Release checklist for the Burger ontology 1.1.0:
   [ok] every term has a label and a definition
   [ok] version IRI matches versionInfo
   [ok] prior version recorded
   [ok] no unknown burger: terms
   [ok] example data passes SHACL
   [ok] CQ1 (which items need a fryer?) answered

Ready to publish: True
```

## How this maps to buildings

> **Buildings box.** The same checklist works for a building model handed over at the end of a project: every
> point labelled and defined, the model's version recorded, no unknown **Brick**, **ASHRAE 223P** or **Haystack**
> terms, the standard SHACL shapes passing, and the FDD competency questions ("does every AHU have the inputs
> each rule needs?") answered.

## Why it matters

Over Weeks 6–9 you wrote triples by hand, gave them meaning with RDFS and OWL, checked them with SHACL, built an
ontology with a method, and learned to publish and maintain it. The same skills, with Brick and 223P instead of
burgers, are how building models are written, checked and kept.

## FUTURE: an Open-FDD ontology

This course teaches the basics that a future Open-FDD ontology extension will build on. That extension would use
its own namespace (`ofdd:`) for the things FDD itself produces (fault results, fault timelines, assessment status,
rule coverage, and which sensor a rule assessed) while using **Haystack**, **Brick** and **ASHRAE 223P** for the
standard building concepts, aligned the way Day 40 shows. It is still being discussed, so this course does not
design it; follow the discussion in
[open-fdd issue #1569](https://github.com/bbartling/open-fdd/issues/1569#issuecomment-6772576346).

## Week 9 further reading

- [w3id.org: creating an identifier](https://docs.w3id.org/guides/create-an-id) and
  [content negotiation](https://docs.w3id.org/guides/content-negotiation)
- W3C, [Best Practice Recipes for Publishing RDF Vocabularies](https://www.w3.org/TR/swbp-vocab-pub/)
- W3C, [OWL 2 Structural Specification: ontology IRIs and version IRIs](https://www.w3.org/TR/owl2-syntax/#Ontology_IRI_and_Version_IRI)
- [Semantic Versioning](https://semver.org/)
- W3C, [SPARQL 1.1 Update](https://www.w3.org/TR/sparql11-update/) and [SHACL](https://www.w3.org/TR/shacl/)
- [Brick: extending Brick](https://docs.brickschema.org/extra/extending.html)

## Try it

1. Add `burger:IceMachine` to `burger.ttl` with a label but no definition. Which check fails?
2. What would you add to the checklist before a *major* (2.0.0) release?
3. **Mini challenge (Burger Barn):** break the release on purpose by deleting the `skos:definition` of
   `burger:Grill`. Which check fails, and which term does it name?

<details><summary>Answers</summary>

1. "every term has a label and a definition".
2. Migration: every deprecated term has a `dcterms:isReplacedBy`, and the migration update has been run on the
   example data and on older test files.
3. **"every term has a label and a definition"** fails, and the missing definition is `Grill`'s. (The course's
   tests check this answer.)

</details>
