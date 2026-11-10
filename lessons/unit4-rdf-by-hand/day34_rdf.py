# Day 34: the menu graph. Follow chains of links: which menu items depend on which equipment?
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day34_rdf.py

from rdflib import Graph

# 1. Load the restaurant, its ontology and its menu into one graph.
#    bb:Fryer_1 in the menu file is the same bb:Fryer_1 as in burger_barn.ttl: same name.
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_barn_ontology.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_barn_menu.ttl")

# 2. Which menu items need a fryer? From each item, follow includes or hasIngredient any
#    number of times (the * in the path), then one cookedOn step. A chain of properties.
fryer_query = """
SELECT DISTINCT ?item ?fryer WHERE {
  bb:BurgerBarn bb:servesItem ?item .
  ?item (bb:includes|bb:hasIngredient)*/bb:cookedOn ?fryer .
  ?fryer a bb:Fryer .
} ORDER BY ?item ?fryer
"""

# 3. If Fryer_2 breaks, what comes off the menu? The same chain, ending at one fryer.
broken_query = """
SELECT DISTINCT ?item WHERE {
  bb:BurgerBarn bb:servesItem ?item .
  ?item (bb:includes|bb:hasIngredient)*/bb:cookedOn bb:Fryer_2 .
}
"""

# 4. Which menu items need the walk-in cooler? (an ingredient is storedIn it)
cooler_query = """
SELECT DISTINCT ?item WHERE {
  bb:BurgerBarn bb:servesItem ?item .
  ?item (bb:includes|bb:hasIngredient)*/bb:storedIn bb:WalkInCooler_1 .
}
"""

on_fryer = [(item.fragment, fryer.fragment) for item, fryer in g.query(fryer_query)]
off_menu = sorted(row.item.fragment for row in g.query(broken_query))
on_cooler = sorted(row.item.fragment for row in g.query(cooler_query))

print("Menu items that need a fryer:")
for item, fryer in on_fryer:
    print("  ", item, "needs", fryer)
print("If Fryer_2 breaks, off the menu:", off_menu)
print("Items that need the walk-in cooler:", on_cooler)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"items_on_fryer": on_fryer, "off_menu_without_fryer_2": off_menu, "on_cooler": on_cooler}
