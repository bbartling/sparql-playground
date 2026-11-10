# Day 38: Ontology Development 101, steps 6-7. Add restrictions to the classes, then create
# instances: one restaurant described with the ontology.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day38_rdf.py

from rdflib import OWL, RDF, RDFS, Graph

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

print("Restrictions (class, property, rule):")
for row in restrictions:
    print("  ", *row)
print(f"\nTBox: {len(tbox)} triples | ABox: {len(abox)} triples")
print("Instances per class:", instance_counts)
print("Classes used in the ABox but not defined in the TBox:", undefined_classes)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "restrictions": restrictions,
    "instance_counts": instance_counts,
    "undefined_classes": undefined_classes,
}
