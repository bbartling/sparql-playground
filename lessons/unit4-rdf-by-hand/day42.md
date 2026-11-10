# Day 42 — Persistent IRIs with w3id.org, redirects and content negotiation

**Goal:** understand how a permanent IRI such as `https://w3id.org/<name>/` works: what a redirect is, how you
would request one, and how one IRI can give a person a web page and a program a Turtle file. (Explanation only:
nothing gets registered.)

## Read

**The problem.** You want `burger:` IRIs that still work in 20 years, even if the files move from one host to
another. **w3id.org** is a free, community-run service for exactly this
([creating an identifier](https://docs.w3id.org/guides/create-an-id)). It doesn't host your files; it **redirects**.

**A redirect** is the server answering "not here, go there": an HTTP status code (`302`, `303`, ...) plus a new
address. Your browser follows it without you noticing. So `https://w3id.org/<name>/` can point at today's host,
and when the files move, only the redirect changes. Every published IRI keeps working.

**How you'd get one (the pull-request flow), in short:**

1. Have your files already online over HTTPS (for example GitHub Pages).
2. Fork the `perma-id/w3id.org` repository on GitHub and add one folder, `ids/<name>/`, holding an `.htaccess`
   file (Apache redirect rules) and optionally a `README.md`, with the maintainers' contact details including a
   GitHub username.
3. Test the rules, open a pull request (one identifier, one squashed commit), and wait for a maintainer to merge.
4. Check it with `curl -sIL https://w3id.org/<name>/`.

The guide recommends `302` for plain redirects and **`303 See Other`** for ontology IRIs, and warns against
`301`, which browsers cache forever.

**Content negotiation.** A browser and rdflib ask for the same IRI, but want different things. Each sends an
`Accept` header saying what it can read; the rules redirect accordingly
([w3id: content negotiation](https://docs.w3id.org/guides/content-negotiation)). The `.htaccess` would look like:

```apache
RewriteEngine on

RewriteCond %{HTTP_ACCEPT} text/turtle
RewriteRule ^$ https://example.github.io/burger/burger.ttl [R=303,L]

RewriteCond %{HTTP_ACCEPT} application/ld\+json
RewriteRule ^$ https://example.github.io/burger/burger.jsonld [R=303,L]

# anything else, browsers included: the human-readable page
RewriteRule ^$ https://example.github.io/burger/index.html [R=303,L]
```

The rules run top to bottom and the **first match wins**, so the specific ones come first and the catch-all default
last. [`day42_rdf.py`](day42_rdf.py) simulates exactly that on your machine: four clients, their `Accept`
headers, where each lands, then what each would receive for `burger:Fryer`: Turtle for programs, a small HTML
page for people.

## Run

```bash
uv run python lessons/course.py run 42
```

```
Who gets what (303 See Other redirects):
   a browser                 -> https://example.github.io/burger/index.html
   rdflib or a triple store  -> https://example.github.io/burger/burger.ttl
   a JSON-LD tool            -> https://example.github.io/burger/burger.jsonld
   curl with no header       -> https://example.github.io/burger/index.html

burger:Fryer as Turtle (9 triples):
@prefix burger: <https://example.org/burger#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

burger:Fryer a owl:Class ;
    rdfs:label "Fryer" ;
    rdfs:isDefinedBy <https://example.org/burger> ;
    rdfs:subClassOf [ a owl:Restriction ;
            owl:onProperty burger:hasPoint ;
            owl:someValuesFrom burger:TemperatureSensor ],
        burger:CookingEquipment ;
    skos:definition "A vat of hot oil that cooks food." .


burger:Fryer as HTML:
<h1>Fryer</h1>
<p>A vat of hot oil that cooks food.</p>
<p>IRI: <code>https://example.org/burger#Fryer</code></p>
```

The browser's header lists `text/html` and `*/*`, matches neither RDF rule, and falls through to the HTML page.
A program that asks for Turtle gets it. The Turtle for `burger:Fryer` includes its restriction, because `cbd()` follows
the `[ ... ]` blank node along with the term's own triples.

## How this maps to buildings

> **Buildings box.** Open `https://brickschema.org/schema/Brick` in a browser and you get a download of the
> current **Brick** release; tools use the same namespace to fetch the ontology. **ASHRAE 223P** publishes its
> model at `http://data.ashrae.org/standard223` with documentation at open223.info, and **Haystack** publishes its
> defs as Turtle at project-haystack.org. A site or vendor extension deserves the same: a stable IRI that serves
> docs to people and Turtle to tools.

## Why it matters

Persistent IRIs are what let a model written today still resolve, and still mean the same thing, years from now.

## Try it

1. Put the default rule first. Which client gets what?
2. Why does the w3id guide say to escape the `+` in `application/ld\+json`?
3. **Mini challenge (Burger Barn):** a client sends `Accept: application/ld+json, text/turtle;q=0.5`. With these
   rules, which file does it get, and why?

<details><summary>Answers</summary>

1. Everyone gets the HTML page: the first rule always matches.
2. In the rule's regular expression `+` means "one or more", so `ld+json` would match `ldjson`, `lddjson` and so
   on, but not the real header text `ld+json`.
3. **`burger.ttl`.** The rules check `text/turtle` first and it appears in the header. Simple rules like these ignore
   the `q=0.5` preference; only rule order matters. (The course's tests check this answer.)

</details>
