# Day 38: Ontology Development 101, steps 6-7. Add restrictions to the classes, then create
# instances: one restaurant described with the ontology, cook methods as named values
# (an enumeration), clean labels, and franchise codes that need their franchise.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day38_rdf.py

from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace

# 1. The ontology (TBox) and one restaurant's facts (ABox)
tbox = Graph().parse("lessons/unit4-rdf-by-hand/burger.ttl")
abox = Graph().parse("lessons/unit4-rdf-by-hand/burger_site.ttl")

# 2. Step 6: restrictions. Each one is an unnamed class [ a owl:Restriction ... ] that a
#    named class is a subClassOf. Read: "every <class> has <some/exactly n> <property> ..."
restrictions = []
for cls, restriction in tbox.subject_objects(RDFS.subClassOf):
    if (restriction, RDF.type, OWL.Restriction) not in tbox:
        continue  # a normal named parent class, not a restriction
    prop = tbox.value(restriction, OWL.onProperty)
    some = tbox.value(restriction, OWL.someValuesFrom)  # "some ..." restriction, or None
    exactly = tbox.value(restriction, OWL.cardinality)  # "exactly n" restriction, or None
    rule = f"some {some.fragment}" if some is not None else f"exactly {exactly}"
    restrictions.append((cls.fragment, prop.fragment, rule))
restrictions.sort()

# 3. Step 7: instances. How many things of each class does the restaurant have?
instance_counts = {}
for _thing, cls in abox.subject_objects(RDF.type):
    instance_counts[cls.fragment] = instance_counts.get(cls.fragment, 0) + 1
instance_counts = dict(sorted(instance_counts.items()))

# 4. Did the instances only use classes the ontology defines?
defined = set(tbox.subjects(RDF.type, OWL.Class))
undefined_classes = sorted(
    {cls.fragment for cls in abox.objects(None, RDF.type)} - {cls.fragment for cls in defined}
)

# 5. Enumerations: the allowed cook methods are named things, each with a name and a code
BURGER = Namespace("https://example.org/burger#")
enums = Graph().parse("lessons/unit4-rdf-by-hand/burger_cook_methods.ttl")
cook_methods = []
for row in enums.query("""
    SELECT ?method ?name ?code WHERE {
      ?method a burger:CookMethodEnumerationValue ; burger:name ?name ; burger:value ?code .
    } ORDER BY ?code"""):
    cook_methods.append((row.method.fragment, str(row.name), int(row.code)))

# 6. Each menu item's cook method. A named value is fine; plain text is a mistake.
items = Graph()
items.parse("lessons/unit4-rdf-by-hand/burger_cook_data.ttl")
items.parse("lessons/unit4-rdf-by-hand/burger_cook_mistakes.ttl")
item_cook_methods = {}
text_not_iri = []
for item, method in sorted(items.subject_objects(BURGER.cookMethod)):
    if isinstance(method, Literal):
        text_not_iri.append(item.fragment)  # "fried" as text: could be misspelled or ambiguous
        item_cook_methods[item.fragment] = f"TEXT {str(method)!r}"
    else:
        item_cook_methods[item.fragment] = str(enums.value(method, BURGER.name))

# 7. Clean labels: a label that starts with a digit has a code packed into it, like "15-..."
coded_labels = sorted(
    str(label) for label in items.objects(None, RDFS.label) if str(label)[0].isdigit()
)

# 8. Franchise specials: "special 7" only means something together with the franchise ID
specials = Graph().parse("lessons/unit4-rdf-by-hand/burger_specials.ttl")
code_7_alone = []
for row in specials.query("""
    SELECT ?name WHERE {
      ?special a burger:FranchiseSpecial ; burger:specialCode 7 ; rdfs:label ?name .
    } ORDER BY ?name"""):
    code_7_alone.append(str(row.name))
receipts = {}
for row in specials.query("""
    SELECT ?receipt ?name WHERE {
      ?receipt burger:franchiseId ?franchise ; burger:specialCode ?code .
      FILTER NOT EXISTS { ?receipt a burger:FranchiseSpecial }
      ?special a burger:FranchiseSpecial ; burger:franchiseId ?franchise ;
               burger:specialCode ?code ; rdfs:label ?name .
    } ORDER BY ?receipt"""):
    receipts[row.receipt.fragment] = str(row.name)

print("Restrictions (class, property, rule):")
for row in restrictions:
    print("  ", *row)
print(f"\nTBox: {len(tbox)} triples | ABox: {len(abox)} triples")
print("Instances per class:", instance_counts)
print("Classes used in the ABox but not defined in the TBox:", undefined_classes)
print("\nCook methods (named value, name, code):", cook_methods)
print("Cook method of each menu item:", item_cook_methods)
print("Cook methods written as text instead of a named value:", text_not_iri)
print("Labels with a code packed in:", coded_labels)
print("\nWhat does 'special 7' mean on its own?", code_7_alone)
print("With the franchise ID, each receipt resolves:", receipts)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "restrictions": restrictions,
    "instance_counts": instance_counts,
    "undefined_classes": undefined_classes,
    "cook_methods": cook_methods,
    "item_cook_methods": item_cook_methods,
    "text_not_iri": text_not_iri,
    "coded_labels": coded_labels,
    "code_7_alone": code_7_alone,
    "receipts": receipts,
}
