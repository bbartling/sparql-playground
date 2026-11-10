# Day 36: Ontology Development 101, steps 1-3. Set the scope, write competency questions,
# look for terms you can reuse, and list the terms you still need.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day36_rdf.py

from rdflib import Graph, URIRef

# Step 1. Scope: what the ontology is for, and what it is NOT for
scope = "Burger restaurant equipment, its sensor points, and which menu items need it."
out_of_scope = ["staff and shifts", "prices and sales", "recipes and cooking steps"]

# ...and competency questions: questions the finished ontology MUST be able to answer.
# Under each, the terms (words) it needs.
competency_questions = {
    "CQ1 Which menu items depend on a fryer?": ["MenuItem", "Fryer", "cookedOn", "hasIngredient"],
    "CQ2 Which equipment has no temperature sensor?": [
        "Equipment",
        "hasPoint",
        "TemperatureSensor",
    ],
    "CQ3 Where is each piece of equipment?": ["Equipment", "hasLocation", "Kitchen"],
    "CQ4 What oil temperature is each fryer set to?": ["Fryer", "oilSetpoint"],
    "CQ5 How many calories is each menu item?": ["MenuItem", "hasCalories"],
}

# Step 3 first, because it's easy: every term the questions need, once each
terms = sorted({term for needed in competency_questions.values() for term in needed})

# Step 2. Reuse: does a standard ontology already have the word? Here: the few Brick terms in
# tiny_building.ttl (the real Brick has about 1,000 classes). Compare names without "_" and case.
brick = Graph().parse("lessons/unit4-rdf-by-hand/tiny_building.ttl")
brick_terms = {}
for triple in brick:
    for term in triple:
        if isinstance(term, URIRef) and str(term).startswith("https://brickschema.org/"):
            brick_terms[term.fragment.replace("_", "").lower()] = term.fragment

reuse = {}
for term in terms:
    match = brick_terms.get(term.lower())
    reuse[term] = f"brick:{match}" if match else None

print("Scope:", scope)
print("Out of scope:", ", ".join(out_of_scope))
print("\nCompetency questions:")
for question, needed in competency_questions.items():
    print("  ", question, "->", ", ".join(needed))
print(f"\nTerms needed ({len(terms)}), and a Brick term with the same name:")
for term, match in reuse.items():
    print(f"   {term:18} {match or '(none: a new burger: term)'}")

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"terms": terms, "reuse": reuse, "questions": len(competency_questions)}
