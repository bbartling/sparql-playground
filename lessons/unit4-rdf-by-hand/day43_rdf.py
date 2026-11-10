# Day 43: versions, deprecation and migration. Read the ontology's version, find the
# deprecated terms, and move an old data file onto the new names with a SPARQL update.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day43_rdf.py

from rdflib import OWL, Graph, Literal, Namespace, URIRef

DCTERMS = Namespace("http://purl.org/dc/terms/")
ONTOLOGY = URIRef("https://example.org/burger")

# 1. The ontology's own description: which version is this?
ontology = Graph().parse("lessons/unit4-rdf-by-hand/burger.ttl")
version = str(ontology.value(ONTOLOGY, OWL.versionInfo))
version_iri = str(ontology.value(ONTOLOGY, OWL.versionIRI))
prior = str(ontology.value(ONTOLOGY, OWL.priorVersion))
#    A cheap consistency check: the version IRI should end with the version number
version_ok = version_iri.endswith("/" + version)

# 2. Deprecated terms, and what replaces each one
deprecated = {}
for term in ontology.subjects(OWL.deprecated, Literal(True)):
    deprecated[term.fragment] = ontology.value(term, DCTERMS.isReplacedBy).fragment

# 3. An old data file (written for 1.0.0) loaded together with the ontology
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_site_v1.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger.ttl")
uses_query = """
SELECT ?thing ?old WHERE { ?thing a ?old . ?old owl:deprecated true } ORDER BY ?thing
"""
before = [(row.thing.fragment, row.old.fragment) for row in g.query(uses_query)]

# 4. Migrate: for every thing typed with a deprecated class, swap in the replacement.
#    One SPARQL UPDATE does it for every deprecated class, now and in future versions.
g.update("""
DELETE { ?thing a ?old }
INSERT { ?thing a ?new }
WHERE  { ?thing a ?old . ?old owl:deprecated true ; dcterms:isReplacedBy ?new }
""")
after = [(row.thing.fragment, row.old.fragment) for row in g.query(uses_query)]
coolers = sorted(row.x.fragment for row in g.query("SELECT ?x WHERE { ?x a burger:WalkInCooler }"))

print(f"Version {version} ({version_iri}), previous: {prior}. Version IRI matches: {version_ok}")
print("Deprecated -> replacement:", deprecated)
print("\nOld data using deprecated classes, before migration:", before)
print("...after migration:", after)
print("Walk-in coolers after migration:", coolers)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "version": version,
    "version_ok": version_ok,
    "deprecated": deprecated,
    "before": before,
    "after": after,
    "coolers": coolers,
}
