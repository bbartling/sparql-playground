# Day 31: RDFS. Classes, the class hierarchy, rdfs:domain and rdfs:range, and what an
# RDFS reasoner may add to your graph (entailment).
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day31_rdf.py

import owlrl
from rdflib import RDFS, Graph, Namespace, URIRef

BB = Namespace("https://example.org/burger-barn#")

# 1. The TBox (the ontology: classes and properties) and the ABox (the facts), kept apart
tbox = Graph().parse("lessons/unit4-rdf-by-hand/burger_barn_ontology.ttl")
abox = Graph().parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")
g = tbox + abox  # one graph with both

# 2. The class tree: every (class, parent class) pair. isinstance(..., URIRef) skips the
#    unnamed [ ... ] restriction you'll meet on Day 33.
parents = sorted(
    (child.fragment, parent.fragment)
    for child, parent in g.subject_objects(RDFS.subClassOf)
    if isinstance(parent, URIRef)
)

# 3. Walk up from Fryer to the top (owl:Thing), one named parent at a time
chain = ["Fryer"]
current = BB.Fryer
while True:
    named = [p for p in g.objects(current, RDFS.subClassOf) if isinstance(p, URIRef)]
    if not named:
        break
    current = named[0]
    chain.append(current.fragment)

# 4. "Which things are Equipment?" Nothing says "a bb:Equipment" directly, so the plain
#    pattern finds nothing. The path a/rdfs:subClassOf* follows the tree up by hand.
exact_query = "SELECT ?thing WHERE { ?thing a bb:Equipment }"
path_query = "SELECT ?thing WHERE { ?thing a/rdfs:subClassOf* bb:Equipment }"
exact = sorted(row.thing.fragment for row in g.query(exact_query))
with_path = sorted(row.thing.fragment for row in g.query(path_query))

# 5. Domain and range are NOT checks: they let a reasoner add types. A new mixer is
#    written with no type at all, only "it has a point"...
g.add((BB.Mixer_1, BB.hasPoint, BB.Mixer_1_Speed))
#    ...and RDFS entailment (rdfs:domain bb:Equipment, rdfs:range bb:Point) types both.
triples_before = len(g)
owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(g)
triples_after = len(g)
types_query = """
SELECT ?thing ?type WHERE {
  VALUES ?thing { bb:Mixer_1 bb:Mixer_1_Speed }
  ?thing a ?type .
  FILTER(STRSTARTS(STR(?type), STR(bb:)))      # only Burger Barn's own classes
} ORDER BY ?thing ?type
"""
new_types = [(row.thing.fragment, row.type.fragment) for row in g.query(types_query)]

print(f"TBox (ontology) {len(tbox)} triples, ABox (facts) {len(abox)} triples")
print("\nClass tree (class -> parent):")
for child, parent in parents:
    print("  ", child, "->", parent)
print("\nFrom Fryer up:", " -> ".join(chain))
print("?thing a bb:Equipment:                ", exact)
print("?thing a/rdfs:subClassOf* bb:Equipment:", with_path)
print("\nRDFS entailment: triples", triples_before, "->", triples_after)
print("Types given to the untyped mixer and its point:", new_types)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "tbox_triples": len(tbox),
    "abox_triples": len(abox),
    "parents": parents,
    "fryer_chain": chain,
    "exact": exact,
    "with_path": with_path,
    "new_types": new_types,
}
