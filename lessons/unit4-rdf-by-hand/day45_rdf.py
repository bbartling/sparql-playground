# Day 45: the release checklist. Everything from Weeks 8-9 in one go, on the real files:
# if every line says ok, version 1.1.0 of the Burger ontology is ready to publish.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day45_rdf.py

from pyshacl import validate
from rdflib import OWL, RDF, RDFS, SKOS, Graph, Namespace, URIRef

BURGER = Namespace("https://example.org/burger#")
ONTOLOGY = URIRef("https://example.org/burger")
FOLDER = "lessons/unit4-rdf-by-hand/"

# 1. The release: the ontology, its shapes, its alignment, and one example data file
ontology = Graph().parse(FOLDER + "burger.ttl")
shapes = Graph().parse(FOLDER + "burger_shapes.ttl")
alignment = Graph().parse(FOLDER + "burger_alignment.ttl")
site = Graph().parse(FOLDER + "burger_site.ttl")

checks = {}

# 2. Every term we define has a label and a definition
ours = {t for t in ontology.subjects(RDF.type, None) if str(t).startswith(str(BURGER))}
undocumented = [t for t in ours if not ontology.value(t, RDFS.label)]
undocumented += [t for t in ours if not ontology.value(t, SKOS.definition)]
checks["every term has a label and a definition"] = not undocumented

# 3. The version IRI ends with the version number, and there is a prior version
version = str(ontology.value(ONTOLOGY, OWL.versionInfo))
version_iri = str(ontology.value(ONTOLOGY, OWL.versionIRI))
checks["version IRI matches versionInfo"] = version_iri.endswith("/" + version)
checks["prior version recorded"] = ontology.value(ONTOLOGY, OWL.priorVersion) is not None

# 4. The alignment and the example data only use burger: terms that exist
used = set(site.predicates()) | set(site.objects(None, RDF.type)) | set(alignment.subjects())
unknown = [t for t in used if str(t).startswith(str(BURGER)) and t not in ours]
checks["no unknown burger: terms"] = not unknown

# 5. The example data passes the shapes
conforms, _report, _text = validate(site + ontology, shacl_graph=shapes)
checks["example data passes SHACL"] = conforms

# 6. A competency question still gets an answer (CQ1 from Day 36)
cq1 = """
SELECT DISTINCT ?item WHERE {
  ?item a burger:MenuItem ; burger:hasIngredient*/burger:cookedOn/a burger:Fryer .
}"""
checks["CQ1 (which items need a fryer?) answered"] = len((site + ontology).query(cq1)) > 0

ready = all(checks.values())
print(f"Release checklist for the Burger ontology {version}:")
for check, passed in checks.items():
    print(f"   [{'ok' if passed else 'FAIL'}] {check}")
print("\nReady to publish:", ready)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"version": version, "checks": checks, "ready": ready}
