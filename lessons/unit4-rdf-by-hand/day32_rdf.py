# Day 32: OWL properties, how things relate. The kinds of property, and what inverse,
# symmetric, transitive, functional and chained properties let you leave unsaid.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day32_rdf.py

import owlrl
from rdflib import OWL, RDF, Graph

# 1. Load the restaurant, its ontology and its menu
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_barn_ontology.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_barn_menu.ttl")

# 2. The three kinds of property, and the special types some of them have
kinds = {}
for kind in [OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty]:
    kinds[kind.fragment] = sorted(p.fragment for p in g.subjects(RDF.type, kind))
types = {}
for kind in [OWL.TransitiveProperty, OWL.SymmetricProperty, OWL.FunctionalProperty]:
    types[kind.fragment] = sorted(p.fragment for p in g.subjects(RDF.type, kind))

# 3. Functional means "at most one value". Does any menu item have two calorie numbers?
two_values_query = """
SELECT ?item WHERE { ?item bb:hasCalories ?calories }
GROUP BY ?item HAVING (COUNT(?calories) > 1)
"""
two_calories = [row.item.fragment for row in g.query(two_values_query)]

# 4. Six questions: (name, plain query, property path that needs no reasoner)
questions = [
    ("subPropertyOf: what does CrispyChicken use?",
     "SELECT ?x WHERE { bb:CrispyChicken bb:usesEquipment ?x }",
     "SELECT ?x WHERE { ?p rdfs:subPropertyOf* bb:usesEquipment . bb:CrispyChicken ?p ?x }"),
    ("inverseOf: who uses Fryer_1?",
     "SELECT ?x WHERE { bb:Fryer_1 bb:isUsedBy ?x }",
     "SELECT ?x WHERE { ?p rdfs:subPropertyOf* bb:usesEquipment . ?x ?p bb:Fryer_1 }"),
    ("inverseOf: whose point is the oil temp?",
     "SELECT ?x WHERE { bb:Fryer_1_OilTemp bb:isPointOf ?x }",
     "SELECT ?x WHERE { bb:Fryer_1_OilTemp ^bb:hasPoint ?x }"),
    ("symmetric: who shares a fryer with CrispyChicken?",
     "SELECT ?x WHERE { bb:CrispyChicken bb:sharesFryerWith ?x }",
     "SELECT ?x WHERE { bb:CrispyChicken bb:sharesFryerWith|^bb:sharesFryerWith ?x }"),
    ("transitive: what is MainKitchen part of?",
     "SELECT ?x WHERE { bb:MainKitchen bb:partOf ?x }",
     "SELECT ?x WHERE { bb:MainKitchen bb:partOf+ ?x }"),
    ("chain: what equipment does ClassicBurger need?",
     "SELECT ?x WHERE { bb:ClassicBurger bb:needsEquipment ?x }",
     "SELECT DISTINCT ?x WHERE { bb:ClassicBurger bb:hasIngredient/(bb:cookedOn|bb:storedIn) ?x }"),
]  # fmt: skip
answers = {}
for name, plain, path in questions:
    answers[name] = {
        "before": sorted(row.x.fragment for row in g.query(plain)),
        "path": sorted(row.x.fragment for row in g.query(path)),
    }

# 5. Let owlrl add every triple the ontology implies, then ask the plain questions again
triples_before = len(g)
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
triples_after = len(g)
for name, plain, _path in questions:  # _path: not needed this time
    answers[name]["after"] = sorted(row.x.fragment for row in g.query(plain))

for kind, names in kinds.items():
    print(f"{kind} ({len(names)}):", ", ".join(names))
for kind, names in types.items():
    print(f"{kind}:", names)
print("Menu items with two calorie numbers:", two_calories)
print("\nTriples: before inference", triples_before, "| after", triples_after)
for name, result in answers.items():
    print("\n" + name)
    print("  plain query, before inference:", result["before"])
    print("  property path, no inference:  ", result["path"])
    print("  plain query, after inference: ", result["after"])

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "kinds": kinds,
    "types": types,
    "two_calories": two_calories,
    "triples_before": triples_before,
    "triples_after": triples_after,
    "answers": answers,
}
