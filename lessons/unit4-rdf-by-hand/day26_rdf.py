# Day 26: load your first hand-written triples with rdflib, count them, and find the typo.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day26_rdf.py

from rdflib import Graph, URIRef

# 1. Load the Turtle file into a graph (a set of triples)
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/day26_first_triples.ttl")

# 2. Print every triple, keeping only the short name after the # (sorted, so it reads well)
print("The graph has", len(g), "triples:")
for subject, predicate, obj in sorted(g):
    print(" ", subject.split("#")[-1], predicate.split("#")[-1], obj.split("#")[-1])

# 3. Count how often each predicate is used. A predicate used only once is suspicious.
predicate_counts = {}
for _subject, predicate, _object in g:  # _ : we don't use these two here
    name = predicate.split("#")[-1]
    predicate_counts[name] = predicate_counts.get(name, 0) + 1

# 4. What does the kitchen contain? None means "anything" in that position.
kitchen = URIRef("https://example.org/burger-barn#Kitchen")
contains = URIRef("https://example.org/burger-barn#contains")
kitchen_contents = sorted(obj.split("#")[-1] for obj in g.objects(kitchen, contains))

print("\nHow often each predicate is used:")
for name, count in sorted(predicate_counts.items()):
    print(" ", name, count)
print("\nThe kitchen contains:", ", ".join(kitchen_contents))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "triple_count": len(g),
    "predicate_counts": predicate_counts,
    "kitchen_contents": kitchen_contents,
}
