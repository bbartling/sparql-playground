# Day 37: Ontology Development 101, steps 4-5. Define the classes and their hierarchy,
# then the properties, in burger.ttl. Check that every term from Day 36 is there and that
# every term has a label and a definition.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day37_rdf.py

from rdflib import OWL, RDF, RDFS, SKOS, Graph, Namespace, URIRef

BURGER = Namespace("https://example.org/burger#")

# 1. Load the ontology (TBox only: no restaurant yet)
g = Graph().parse("lessons/unit4-rdf-by-hand/burger.ttl")

# 2. Step 4: classes, with their named parent class (None at the top)
classes = []
for cls in sorted(g.subjects(RDF.type, OWL.Class)):
    named = [p.fragment for p in g.objects(cls, RDFS.subClassOf) if isinstance(p, URIRef)]
    classes.append((cls.fragment, named[0] if named else None))

# 3. Step 5: properties, with their kind, domain and range
properties = []
for kind in [OWL.ObjectProperty, OWL.DatatypeProperty]:
    for prop in sorted(g.subjects(RDF.type, kind)):
        domain = g.value(prop, RDFS.domain)
        range_ = g.value(prop, RDFS.range)
        properties.append(
            (
                prop.fragment,
                kind.fragment,
                domain.fragment if domain else None,
                range_.fragment if range_ else None,
            )
        )

# 4. Did we define every term Day 36's competency questions need?
needed = ["Equipment", "Fryer", "Kitchen", "MenuItem", "TemperatureSensor", "cookedOn"]
needed += ["hasCalories", "hasIngredient", "hasLocation", "hasPoint", "oilSetpoint"]
defined = {s for s in g.subjects(RDF.type, None) if str(s).startswith(str(BURGER))}
missing_terms = [term for term in needed if BURGER[term] not in defined]

# 5. Good manners for a published ontology: a label and a definition on every term
no_label = sorted(t.fragment for t in defined if g.value(t, RDFS.label) is None)
no_definition = sorted(t.fragment for t in defined if g.value(t, SKOS.definition) is None)

print("Classes (class, parent):")
for name, parent in classes:
    print(f"   {name:18} {parent}")
print("\nProperties (name, kind, domain, range):")
for row in properties:
    print(f"   {row[0]:14} {row[1]:18} {row[2]!s:12} {row[3]}")
print("\nTerms the competency questions need but burger.ttl lacks:", missing_terms)
print("Terms without a label:", no_label, "| without a definition:", no_definition)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "classes": classes,
    "properties": properties,
    "missing_terms": missing_terms,
    "no_label": no_label,
    "no_definition": no_definition,
}
