# Day 41 — Namespaces and IRIs: choosing names that last

**Goal:** take an IRI apart, see why the same local name in two namespaces means two different things, and choose a
namespace you'll never have to change.

## Read

Week 9 is about **publishing** the Burger ontology so other people (and programs) can use it. It starts with names.
Every term's full name is an **IRI**: a **namespace** plus a **local name**.

```
https://example.org/burger#Fryer
└─────── namespace ───────┘└local┘
```

The prefix `burger:` is only a local nickname for the namespace; another file may call it `bk:` and mean the same
thing. What counts is the full IRI. So `bb:Fryer` (Weeks 6–7) and `burger:Fryer` (Weeks 8–9) are **different
classes**: same four letters, different namespaces. RDF never guesses that two names are the same thing; if they
are, you say so (Day 40).

**Choosing a namespace.** Once data uses your terms, changing the namespace breaks every file and query that uses
them. So choose once, carefully:

| Do | Don't |
|---|---|
| use a domain you control for decades, or a **persistent IRI** service such as w3id.org (Day 42) | use a personal laptop name, a dev server or an IP address |
| keep version numbers *out* of term IRIs (`burger#Fryer`, not `burger/1.1#Fryer`) | put the version in every term: each release would rename everything |
| pick `#` (one file serves every term) or `/` (one page per term) and stick to it | mix them |
| use `https://example.org/` only for examples, as this course does | publish real terms under example.org |

Brick's own namespace is `https://brickschema.org/schema/Brick#`; ASHRAE 223P's is `http://data.ashrae.org/standard223#`.
Both use `#`, and Brick has kept the same namespace across releases.

[`day41_rdf.py`](day41_rdf.py) takes one IRI apart, counts the terms each namespace contributes when both
restaurants' files are loaded together, and asks for "Fryer" in both namespaces.

## Run

```bash
uv run python lessons/course.py run 41
```

```
Anatomy of https://example.org/burger#Fryer
   scheme     https
   host       example.org
   path       /burger
   local name Fryer

Terms per namespace:
     1  http://www.w3.org/1999/02/22-rdf-syntax-ns#
     5  http://www.w3.org/2000/01/rdf-schema#
     2  http://www.w3.org/2001/XMLSchema#
    15  http://www.w3.org/2002/07/owl#
     1  http://www.w3.org/2004/02/skos/core#
    21  https://example.org/burger#
    40  https://example.org/burger-barn#
    15  https://example.org/burger-site#

?x a bb:Fryer     -> ['https://example.org/burger-barn#Fryer_1', 'https://example.org/burger-barn#Fryer_2']
?x a burger:Fryer -> ['https://example.org/burger-site#Fryer_1', 'https://example.org/burger-site#Fryer_2']
```

Two `Fryer_1`s, two different things, and no query for one ever finds the other.

## How this maps to buildings

> **Buildings box.** Every building model mixes namespaces: **Brick** (`brick:`), **ASHRAE 223P** (`s223:`), QUDT
> for units, and the site's own namespace for its equipment and points. Give each site a stable namespace of its
> own on day one; renaming `AHU_1`'s IRI later breaks every FDD result and trend that refers to it.
> **Haystack** ids (`@AHU_1`) become IRIs in the site's namespace when exported to RDF.

## Why it matters

A published IRI is a promise. Choose it like a street address you can never move.

## Try it

1. What are the namespace and local name of `http://www.w3.org/2000/01/rdf-schema#label`?
2. Why is `https://192.168.1.20/burger#Fryer` a bad namespace?
3. **Mini challenge (Burger Barn):** how many different `burger:` terms appear in `burger.ttl` alone?

<details><summary>Answers</summary>

1. Namespace `http://www.w3.org/2000/01/rdf-schema#`, local name `label`.
2. It's a private address on one network: it can't be looked up from anywhere else, and it changes when the
   server does.
3. **21.**

   ```sparql
   SELECT (COUNT(DISTINCT ?term) AS ?n) WHERE {
     { ?term ?p ?o } UNION { ?s ?term ?o } UNION { ?s ?p ?term }
     FILTER(isIRI(?term) && STRSTARTS(STR(?term), STR(burger:)))
   }
   ```

   (The course's tests check this answer.)

</details>
