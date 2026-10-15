# Day 56 — Week 8 independent challenge — a model-driven SQL analytics report

[Previous: Day 55](day55.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 57](day57.md)

**Week 8 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 50–55, or equivalent skills.

## Project brief

Build an independently written report whose equipment and point selection comes from the course RDF model, then whose calculations run in SQL over bounded history. Cover observed runtime, energy and one of comfort or the teaching pressure condition. A reviewer should be able to follow the path from semantic discovery to a number and back to evidence.

## Acceptance criteria

- SPARQL discovers all three AHUs and required points by explicit class, ownership and role; labels do not supply identity.
- Every selected point has one external reference, one opaque timeseries ID and one database. Role and unit audits reject missing or ambiguous inputs.
- SQL uses the adapter's explicit IDs, site scope, bound values and half-open reporting window. No IRI parsing or source-column lookup substitutes for reference resolution.
- Full-window observed runtime totals 48 equipment-hours and observed energy totals 467 kWh, with power coverage stated.
- Detail, summary and chosen additional metric retain their declared grain, units and policy.
- Model evidence identifies the captured artifact; the report distinguishes offline fixture validation from live API evidence.

## Deliverables

Submit your SPARQL, SQL, adapter contract, compact results and a short architecture note. Include one negative case for a broken reference or incompatible unit, plus one numerical counterexample involving missing coverage. Keep any web/API inspection separate from the course database result.

## Self-review

Could the store change without rewriting the analytics selection logic? Could a graph revision invalidate a cached mapping? Explain which validations happen before history reads and which happen before calculating the final metric.

Label results **observed**, **fixture-only**, or **not run**. This page intentionally provides no worked solution or implementation sequence. Attempt the challenge independently before consulting [the week’s references](SOURCES.md#week-8).

[Previous: Day 55](day55.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 57](day57.md)
