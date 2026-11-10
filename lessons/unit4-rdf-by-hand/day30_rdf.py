# Day 30: SPARQL as a checker. Find what is MISSING: a fryer with no temperature point,
# a thing with no label, a label that is blank.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day30_rdf.py

from rdflib import Graph

# 1. Load the restaurant
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")

# 2. Which fryer has NO temperature point? FILTER NOT EXISTS: "keep it if there is no match".
no_temp_query = """
SELECT ?fryer WHERE {
  ?fryer a bb:Fryer .
  FILTER NOT EXISTS { ?fryer bb:hasPoint ?point . ?point a bb:TemperatureSensor }
}
"""

# 3. Equipment in the kitchen with a MISSING label: OPTIONAL, then keep rows where it stayed unbound
missing_query = """
SELECT ?thing WHERE {
  bb:MainKitchen bb:contains ?thing .
  OPTIONAL { ?thing rdfs:label ?label }
  FILTER(!BOUND(?label))
}
"""

# 4. ...and with a BLANK label: the label exists, but its text has length 0
blank_query = """
SELECT ?thing WHERE {
  bb:MainKitchen bb:contains ?thing .
  ?thing rdfs:label ?label .
  FILTER(STRLEN(?label) = 0)
}
"""

no_temp = sorted(row.fryer.fragment for row in g.query(no_temp_query))
missing = sorted(row.thing.fragment for row in g.query(missing_query))
blank = sorted(row.thing.fragment for row in g.query(blank_query))

print("Fryers with no temperature point:", no_temp)
print("Kitchen equipment with no label at all:", missing)
print("Kitchen equipment with a blank label:", blank)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fryers_without_temp": no_temp, "missing_labels": missing, "blank_labels": blank}
