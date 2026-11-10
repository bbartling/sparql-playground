# Day 29: ask Burger Barn questions in SPARQL: patterns, OPTIONAL, ORDER BY, COUNT.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day29_rdf.py

from rdflib import Graph

# 1. Load the restaurant. The queries can say bb: and rdfs: because the Turtle file
#    declared those prefixes (in a query of your own you'd write PREFIX lines at the top).
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")

# 2. What is in the kitchen? ?thing is a variable: "find every ?thing that fits".
#    OPTIONAL keeps a row even when the thing has no label.
kitchen_query = """
SELECT ?thing ?label WHERE {
  bb:MainKitchen bb:contains ?thing .
  OPTIONAL { ?thing rdfs:label ?label }
} ORDER BY ?thing
"""

# 3. Which equipment has a temperature sensor? Two patterns that share ?sensor (a join).
temp_query = """
SELECT ?equipment ?sensor WHERE {
  ?equipment bb:hasPoint ?sensor .
  ?sensor a bb:TemperatureSensor .
} ORDER BY ?equipment
"""

# 4. How many things does each room contain? GROUP BY + COUNT, like SQL.
count_query = """
SELECT ?room (COUNT(?thing) AS ?things) WHERE {
  bb:BurgerBarn bb:contains ?room .
  ?room bb:contains ?thing .
} GROUP BY ?room ORDER BY ?room
"""

# 5. Run them. Each result row is a tuple; .fragment is the short name after the #.
kitchen = []
for thing, label in g.query(kitchen_query):
    kitchen.append((thing.fragment, None if label is None else str(label)))
with_temp = [(equipment.fragment, sensor.fragment) for equipment, sensor in g.query(temp_query)]
per_room = [(room.fragment, things.toPython()) for room, things in g.query(count_query)]

print("In the kitchen (name, label):")
for name, label in kitchen:
    print("  ", name, repr(label))
print("Equipment with a temperature sensor:", with_temp)
print("Things per room:", per_room)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"kitchen": kitchen, "equipment_with_temp": with_temp, "per_room": per_room}
