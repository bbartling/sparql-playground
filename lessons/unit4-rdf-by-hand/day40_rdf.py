# Day 40: reuse, the second half. Align your terms to a standard (Brick) so that one query
# finds equipment in a building AND in a burger kitchen.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day40_rdf.py

import owlrl
from rdflib import Graph

# 1. A tiny Brick building, the burger ontology, one restaurant, and the alignment links
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/tiny_building.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_site.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_alignment.ttl")

# 2. Brick-only questions. They never mention burger: at all.
questions = {
    "brick:Equipment": "SELECT ?x WHERE { ?x a/rdfs:subClassOf* brick:Equipment }",
    "brick:Temperature_Sensor": "SELECT ?x WHERE {?x a/rdfs:subClassOf* brick:Temperature_Sensor}",
    "brick:hasPoint": "SELECT ?x WHERE { ?p rdfs:subPropertyOf* brick:hasPoint . ?x ?p ?point }",
    "brick:Building": "SELECT ?x WHERE { ?x a/rdfs:subClassOf* brick:Building }",
}
answers = {}
for name, query in questions.items():
    answers[name] = {"no_reasoner": sorted({row.x.fragment for row in g.query(query)})}

# 3. With a reasoner, owl:equivalentClass counts too (the property paths above don't follow it)
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
for name, query in questions.items():
    answers[name]["reasoner"] = sorted({row.x.fragment for row in g.query(query)})

for name, result in answers.items():
    print(name)
    print("   no reasoner:", result["no_reasoner"])
    print("   reasoner:   ", result["reasoner"])

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"answers": answers}
