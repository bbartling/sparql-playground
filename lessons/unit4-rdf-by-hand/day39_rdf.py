# Day 39: Ontology Development 101, step 8. Test it: answer every competency question with
# SPARQL, and validate the instances with SHACL.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day39_rdf.py

from pyshacl import validate
from rdflib import Graph

# 1. Ontology + one restaurant, and the rules in their own file
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_site.ttl")
shapes = Graph().parse("lessons/unit4-rdf-by-hand/burger_shapes.ttl")

# 2. Day 36's competency questions, now as SPARQL (burger: and site: come from the files)
competency_questions = {
    "CQ1 Which menu items depend on a fryer?": """
        SELECT DISTINCT ?item WHERE {
          ?item a burger:MenuItem ; burger:hasIngredient*/burger:cookedOn ?equipment .
          ?equipment a burger:Fryer .
        } ORDER BY ?item""",
    "CQ2 Which equipment has no temperature sensor?": """
        SELECT ?equipment WHERE {
          ?equipment a/rdfs:subClassOf* burger:Equipment .
          FILTER NOT EXISTS { ?equipment burger:hasPoint/a burger:TemperatureSensor }
        } ORDER BY ?equipment""",
    "CQ3 Where is each piece of equipment?": """
        SELECT ?equipment ?space WHERE { ?equipment burger:hasLocation ?space }
        ORDER BY ?equipment""",
    "CQ4 What oil temperature is each fryer set to?": """
        SELECT ?fryer ?setpoint WHERE { ?fryer a burger:Fryer ; burger:oilSetpoint ?setpoint }
        ORDER BY ?fryer""",
    "CQ5 How many calories is each menu item?": """
        SELECT ?item ?calories WHERE { ?item burger:hasCalories ?calories } ORDER BY ?item""",
}
answers = {}
for question, query in competency_questions.items():
    rows = []
    for row in g.query(query):
        rows.append(
            tuple(term.fragment if hasattr(term, "fragment") else str(term) for term in row)
        )
    answers[question] = rows

# 3. Every question should have an answer. An empty one means a term or a fact is missing.
unanswered = [question for question, rows in answers.items() if not rows]

# 4. SHACL: is the data complete enough to be used?
conforms, report, text = validate(g, shacl_graph=shapes)

for question, rows in answers.items():
    print(question)
    print("  ", rows)
print("\nUnanswered questions:", unanswered)
print("Data follows the shapes:", conforms)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"answers": answers, "unanswered": unanswered, "conforms": conforms}
