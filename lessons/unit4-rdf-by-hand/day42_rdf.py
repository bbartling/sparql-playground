# Day 42: persistent IRIs and content negotiation, simulated on your own machine.
# One IRI, two audiences: a browser gets an HTML page, a program gets Turtle.
# Nothing is registered or sent anywhere: this only shows the idea.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day42_rdf.py

from rdflib import RDFS, SKOS, Graph, Namespace

BURGER = Namespace("https://example.org/burger#")

# 1. The redirect rules, top to bottom, like the .htaccess file you would send to w3id.org.
#    The first rule whose pattern appears in the Accept header wins; the last one is the default.
rules = [
    ("text/turtle", "https://example.github.io/burger/burger.ttl"),
    ("application/ld+json", "https://example.github.io/burger/burger.jsonld"),
    (None, "https://example.github.io/burger/index.html"),  # None: anything else
]

# 2. What different clients send in their Accept header, and where each one ends up
clients = {
    "a browser": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "rdflib or a triple store": "text/turtle",
    "a JSON-LD tool": "application/ld+json",
    "curl with no header": "*/*",
}
redirects = {}
for client, accept in clients.items():
    for pattern, target in rules:
        if pattern is None or pattern in accept:
            redirects[client] = target
            break

# 3. What the Turtle file says about one term, burger:Fryer. cbd() ("concise bounded
#    description") takes the term's own triples plus the [ ... ] blank nodes they point to.
ontology = Graph().parse("lessons/unit4-rdf-by-hand/burger.ttl")
about_fryer = ontology.cbd(BURGER.Fryer)
about_fryer.bind("burger", BURGER)
turtle = about_fryer.serialize(format="turtle")

# 4. ...and the human page a browser would get for the same term
label = ontology.value(BURGER.Fryer, RDFS.label)
definition = ontology.value(BURGER.Fryer, SKOS.definition)
html = f"<h1>{label}</h1>\n<p>{definition}</p>\n<p>IRI: <code>{BURGER.Fryer}</code></p>"

print("Who gets what (303 See Other redirects):")
for client, target in redirects.items():
    print(f"   {client:25} -> {target}")
print(f"\nburger:Fryer as Turtle ({len(about_fryer)} triples):\n{turtle}")
print("burger:Fryer as HTML:\n" + html)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"redirects": redirects, "fryer_triples": len(about_fryer)}
