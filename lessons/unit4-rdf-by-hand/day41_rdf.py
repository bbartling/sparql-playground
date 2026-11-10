# Day 41: namespaces and IRIs. Every term's full name is an IRI: a namespace plus a
# local name. Same local name in two namespaces = two different things.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day41_rdf.py

from urllib.parse import urlparse

from rdflib import Graph, URIRef

# 1. Weeks 6-7's restaurant (bb:) and Weeks 8-9's (burger: and site:) in one graph
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_site.ttl")

# 2. The parts of one IRI
iri = "https://example.org/burger#Fryer"
parts = urlparse(iri)
anatomy = {
    "scheme": parts.scheme,
    "host": parts.netloc,
    "path": parts.path,
    "local name": parts.fragment,  # the part after the #
}

# 3. How many different terms each namespace contributes (split each IRI at its last #)
per_namespace = {}
for triple in g:
    for term in triple:
        if isinstance(term, URIRef) and "#" in term:
            namespace = str(term).rsplit("#", 1)[0] + "#"
            per_namespace.setdefault(namespace, set()).add(term)
counts = {namespace: len(terms) for namespace, terms in sorted(per_namespace.items())}

# 4. Two classes called "Fryer". To RDF they share nothing but four letters.
# Both have a Fryer_1, but the full names (IRIs) differ, so they are different things.
bb_fryers = sorted(str(row.x) for row in g.query("SELECT ?x WHERE { ?x a bb:Fryer }"))
burger_fryers = sorted(str(row.x) for row in g.query("SELECT ?x WHERE { ?x a burger:Fryer }"))

print("Anatomy of", iri)
for part, value in anatomy.items():
    print(f"   {part:10} {value}")
print("\nTerms per namespace:")
for namespace, count in counts.items():
    print(f"   {count:3}  {namespace}")
print("\n?x a bb:Fryer     ->", bb_fryers)
print("?x a burger:Fryer ->", burger_fryers)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "anatomy": anatomy,
    "counts": counts,
    "bb_fryers": bb_fryers,
    "burger_fryers": burger_fryers,
}
