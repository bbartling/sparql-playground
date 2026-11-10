# Day 27: prefixes, rdf:type and rdfs:label. Load Burger Barn and list what is in it.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day27_rdf.py

from rdflib import RDF, RDFS, Graph, Literal, Namespace

BB = Namespace("https://example.org/burger-barn#")  # BB.Fryer_1 is the full IRI of bb:Fryer_1

# 1. Load the restaurant
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")

# 2. Everything that has a type (rdf:type, written "a" in Turtle), with its label
things = []
for thing, kind in sorted(g.subject_objects(RDF.type)):
    label = g.value(thing, RDFS.label)  # one value, or None if there is no such triple
    if label is not None:
        label = str(label)  # a Literal is a kind of string; str() keeps just the text
    things.append((thing.fragment, kind.fragment, label))  # .fragment: the part after the #

# 3. URIs vs literals: what does Fryer 1 point at?
fryer_1 = []
for predicate, obj in sorted(g.predicate_objects(BB.Fryer_1)):
    kind = "literal" if isinstance(obj, Literal) else "URI"
    fryer_1.append((predicate.fragment, str(obj).split("#")[-1], kind))

# 4. How many things of each type?
type_counts = {}
for kind in g.objects(None, RDF.type):  # None means "any subject"
    type_counts[kind.fragment] = type_counts.get(kind.fragment, 0) + 1

print("The graph has", len(g), "triples and", len(things), "typed things:")
for name, kind, label in things:
    print(f"  {name:20} a {kind:18} label: {label!r}")
print("\nFryer_1's triples:")
for predicate, obj, kind in fryer_1:
    print(f"  {predicate:14} {obj:20} ({kind})")
print("\nThings per type:", dict(sorted(type_counts.items())))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "triple_count": len(g),
    "typed_things": len(things),
    "type_counts": type_counts,
    "unlabeled": [name for name, kind, label in things if label is None],
    "blank_labels": [name for name, kind, label in things if label == ""],
}
