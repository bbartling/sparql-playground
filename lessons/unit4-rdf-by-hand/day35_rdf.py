# Day 35: a SHACL rule catches the fryer with no temperature point, then the same patterns
# on a tiny building (an AHU, two VAVs, Brick classes).
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day35_rdf.py

from pyshacl import validate
from rdflib import Graph

# 1. The restaurant (facts + ontology, so the rules know a Fryer is Equipment) and its rules
restaurant = Graph()
restaurant.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")
restaurant.parse("lessons/unit4-rdf-by-hand/burger_barn_ontology.ttl")
restaurant_rules = Graph().parse("lessons/unit4-rdf-by-hand/burger_barn_shapes.ttl")

# 2. The building (it carries its own few Brick subClassOf facts) and its rule
building = Graph().parse("lessons/unit4-rdf-by-hand/tiny_building.ttl")
building_rules = Graph().parse("lessons/unit4-rdf-by-hand/tiny_building_shapes.ttl")

# 3. Check both. validate() returns: conforms (True/False), a report graph and a report text.
#    The report graph has one sh:ValidationResult per problem: which thing (sh:focusNode),
#    how bad (sh:resultSeverity) and which rule's message (sh:resultMessage).
problem_query = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
SELECT ?thing ?severity ?message WHERE {
  ?result a sh:ValidationResult ;
          sh:focusNode ?thing ; sh:resultSeverity ?severity ; sh:resultMessage ?message .
} ORDER BY ?thing ?message
"""
restaurant_ok, restaurant_report, text = validate(restaurant, shacl_graph=restaurant_rules)
building_ok, building_report, text = validate(building, shacl_graph=building_rules)
restaurant_problems = [
    (t.fragment, sev.fragment, str(m)) for t, sev, m in restaurant_report.query(problem_query)
]
building_problems = [
    (t.fragment, sev.fragment, str(m)) for t, sev, m in building_report.query(problem_query)
]

# 4. Week 6's questions, asked of the building. Only the words change.
#    (brick:, ex: and rdfs: come from the prefixes in tiny_building.ttl.)
in_building_query = "SELECT ?equipment WHERE { ?equipment brick:hasLocation ex:Building_1 }"
temp_query = """
SELECT ?equipment ?sensor WHERE {
  ?equipment brick:hasPoint ?sensor .
  ?sensor a/rdfs:subClassOf* brick:Temperature_Sensor .   # any kind of temperature sensor
} ORDER BY ?equipment
"""
# Everything downstream of AHU_1: follow brick:feeds one or more times (feeds+), like contains+
downstream_query = "SELECT ?thing WHERE { ex:AHU_1 brick:feeds+ ?thing }"
in_building = sorted(row.equipment.fragment for row in building.query(in_building_query))
downstream = sorted(row.thing.fragment for row in building.query(downstream_query))
with_temp = [(e.fragment, s.fragment) for e, s in building.query(temp_query)]

print("Restaurant follows its rules:", restaurant_ok)
for thing, severity, message in restaurant_problems:
    print(f"   {thing:15} {severity:10} {message}")
print("Building follows its rules:", building_ok)
for thing, severity, message in building_problems:
    print(f"   {thing:15} {severity:10} {message}")
print("\nEquipment in the building:", in_building)
print("Building equipment with a temperature sensor:", with_temp)
print("Downstream of AHU_1 (brick:feeds+):", downstream)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "restaurant_ok": restaurant_ok,
    "restaurant_problems": restaurant_problems,
    "building_ok": building_ok,
    "building_problems": building_problems,
    "in_building": in_building,
    "building_equipment_with_temp": with_temp,
    "downstream_of_ahu_1": downstream,
}
