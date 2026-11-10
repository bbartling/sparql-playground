# Day 39: Ontology Development 101, step 8. Test it: answer every competency question with
# SPARQL, and validate the instances with SHACL. Then compare two ways to attach a shape:
# a separate shapes file with sh:targetClass, and a class that is its own shape.
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

# 5. Two ways to attach a shape, on the cook-method data (Day 38) plus its three mistakes.
cook_data = Graph()
cook_data.parse("lessons/unit4-rdf-by-hand/burger.ttl")  # so FriedMenuItem counts as a MenuItem
cook_data.parse("lessons/unit4-rdf-by-hand/burger_cook_methods.ttl")
cook_data.parse("lessons/unit4-rdf-by-hand/burger_cook_data.ttl")
cook_data.parse("lessons/unit4-rdf-by-hand/burger_cook_mistakes.ttl")

# 5a. A separate shapes file: MenuItemCookShape has sh:targetClass burger:MenuItem
separate_shapes = Graph().parse("lessons/unit4-rdf-by-hand/burger_cook_shapes.ttl")
# 5b. The class is the shape: burger:FriedMenuItem is a class AND an sh:NodeShape
class_as_shape = Graph().parse("lessons/unit4-rdf-by-hand/burger_cook_methods.ttl")

shape_results = {}
for name, shapes_graph in [("separate file", separate_shapes), ("class is shape", class_as_shape)]:
    _conforms, report_graph, _text = validate(cook_data, shacl_graph=shapes_graph)
    rows = []
    for row in report_graph.query("""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        SELECT ?item ?severity ?message WHERE {
          ?result sh:focusNode ?item ; sh:resultSeverity ?severity ; sh:resultMessage ?message .
        } ORDER BY ?item"""):
        rows.append((row.item.fragment, row.severity.fragment, str(row.message)))
    shape_results[name] = rows

for question, rows in answers.items():
    print(question)
    print("  ", rows)
print("\nUnanswered questions:", unanswered)
print("Data follows the shapes:", conforms)
for name, rows in shape_results.items():
    print(f"\nCook-method check, {name}:")
    for row in rows:
        print("  ", *row)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "answers": answers,
    "unanswered": unanswered,
    "conforms": conforms,
    "shape_results": shape_results,
}
