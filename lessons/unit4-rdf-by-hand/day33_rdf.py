# Day 33: OWL classes. owl:Thing, disjoint classes, a restriction, and the open world:
# why OWL does not complain about a missing value, and SHACL does.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day33_rdf.py

import owlrl
from pyshacl import validate
from rdflib import RDF, Graph, Namespace, URIRef

BB = Namespace("https://example.org/burger-barn#")
# owlrl writes each problem it finds as a triple: (problem, ERROR, "the message")
ERROR = URIRef("http://www.daml.org/2002/03/agents/agent-ont#error")

# 1. Load the facts and the ontology, and let the OWL reasoner add what they imply
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")
g.parse("lessons/unit4-rdf-by-hand/burger_barn_ontology.ttl")
triples_before = len(g)
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
triples_after = len(g)

# 2. owl:Thing is the top class: after inference every named thing is one
fryer_types = sorted(t.fragment for t in g.objects(BB.Fryer_1, RDF.type) if isinstance(t, URIRef))
things = len(set(g.subjects(RDF.type, URIRef("http://www.w3.org/2002/07/owl#Thing"))))

# 3. Problems OWL found in the real data. Fryer_2 has no temperature point, and the
#    ontology says every fryer has one (a restriction). OWL still finds nothing wrong:
errors = [str(message) for message in g.objects(None, ERROR)]

# 4. A typing mistake on a fresh copy: the ice machine (Refrigeration) is also typed a
#    Grill (CookingEquipment). The ontology says those classes are disjoint: OWL catches it.
mistake = Graph()
mistake.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")
mistake.parse("lessons/unit4-rdf-by-hand/burger_barn_ontology.ttl")
mistake.add((BB.IceMachine_1, RDF.type, BB.Grill))
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(mistake)
mistake_errors = [str(message) for message in mistake.objects(None, ERROR)]

# 5. Closed world: SHACL checks only what is written down, so it does see the missing point
data = Graph()
data.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")
data.parse("lessons/unit4-rdf-by-hand/burger_barn_ontology.ttl")
rules = Graph().parse("lessons/unit4-rdf-by-hand/burger_barn_shapes.ttl")
conforms, report, _text = validate(data, shacl_graph=rules)
shacl_query = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
SELECT ?message WHERE { ?r sh:focusNode bb:Fryer_2 ; sh:resultMessage ?message }
ORDER BY ?message
"""
shacl_fryer_2 = [str(row.message) for row in report.query(shacl_query, initNs={"bb": BB})]

print("Triples: before inference", triples_before, "| after", triples_after)
print("Fryer_1 is a:", fryer_types)
print("Things that are an owl:Thing after inference:", things)
print("\nOWL problems in the real data:", errors, "<- open world: nothing missing to OWL")
print("OWL problems after typing IceMachine_1 as a Grill too:")
for message in mistake_errors:
    print("  ", message.replace(str(BB), "bb:"))
print("SHACL problems with Fryer_2 (closed world):", shacl_fryer_2)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "fryer_types": fryer_types,
    "errors": errors,
    "mistake_errors": len(mistake_errors),
    "shacl_fryer_2": shacl_fryer_2,
}
