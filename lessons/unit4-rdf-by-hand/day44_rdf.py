# Day 44: a CI-style check. Before a release, load the ontology plus synthetic test data,
# run the SHACL rules, and run a "doctor" query that sorts every term the data uses into
# standard, custom (ours), deprecated and unknown. Any unknown term or violation = FAIL.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day44_rdf.py

from pyshacl import validate
from rdflib import OWL, RDF, Graph, Literal

# Namespaces we accept as standard: W3C vocabularies and Brick
STANDARD = [
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2002/07/owl#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/2004/02/skos/core#",
    "http://purl.org/dc/terms/",
    "https://brickschema.org/schema/Brick#",
]

# 1. The pieces a CI job would load from the repo
ontology = Graph().parse("lessons/unit4-rdf-by-hand/burger.ttl")
shapes = Graph().parse("lessons/unit4-rdf-by-hand/burger_shapes.ttl")
data = Graph().parse("lessons/unit4-rdf-by-hand/burger_ci_data.ttl")

# 2. The doctor: every property and every class the DATA uses
used = set(data.predicates()) | set(data.objects(None, RDF.type))
defined = set(ontology.subjects(RDF.type, None))
deprecated_terms = set(ontology.subjects(OWL.deprecated, Literal(True)))
report = {"standard": [], "custom": [], "deprecated": [], "unknown": []}
for term in sorted(used):
    if any(str(term).startswith(namespace) for namespace in STANDARD):
        report["standard"].append(term.fragment)
    elif term in deprecated_terms:
        report["deprecated"].append(term.fragment)
    elif term in defined:
        report["custom"].append(term.fragment)
    else:
        report["unknown"].append(str(term))  # full IRI: we don't know where it belongs

# 3. The SHACL rules, on data + ontology (so the rules know a Fryer is Equipment)
conforms, results, text = validate(data + ontology, shacl_graph=shapes)
violations = sorted(
    (row.thing.fragment, str(row.message))
    for row in results.query("""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        SELECT ?thing ?message WHERE { ?r sh:focusNode ?thing ; sh:resultMessage ?message }
    """)
)

# 4. The verdict
ci_passes = conforms and not report["unknown"] and not report["deprecated"]

for kind, terms in report.items():
    print(f"{kind:10} ({len(terms)}): {terms}")
print("\nSHACL violations:", violations)
print("\nCI result:", "PASS" if ci_passes else "FAIL")

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"report": report, "violations": violations, "ci_passes": ci_passes}
