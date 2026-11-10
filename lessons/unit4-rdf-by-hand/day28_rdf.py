# Day 28: literals and their XSD datatypes, and why a number in quotes is a trap.
# Run from the repo root:
#     uv run python lessons/unit4-rdf-by-hand/day28_rdf.py

from rdflib import Graph, Namespace

BB = Namespace("https://example.org/burger-barn#")

# 1. Load the restaurant
g = Graph()
g.parse("lessons/unit4-rdf-by-hand/burger_barn.ttl")

# 2. A few literals: the text in the file, its datatype, and the Python value rdflib makes
examples = [
    (BB.Fryer_1_OilTemp, BB.unit),  # xsd:string   plain text
    (BB.BurgerBarn, BB.seats),  # xsd:integer  whole number
    (BB.WalkInCooler_1, BB.airSetpointC),  # xsd:decimal  number with a decimal point
    (BB.BurgerBarn, BB.isOpen),  # xsd:boolean  true / false
    (BB.BurgerBarn, BB.openedOn),  # xsd:date     a day
    (BB.Fryer_1, BB.lastInspected),  # xsd:dateTime a day and a time
    (BB.BurgerBarn, BB.opensAt),  # xsd:time     a time of day
    (BB.Fryer_1, BB.fryTime),  # xsd:duration how long (PT3M = 3 minutes)
    (BB.Fryer_1, BB.oilSetpointC),  # a number...
    (BB.Fryer_2, BB.oilSetpointC),  # ...and the same number in quotes: text!
]
literals = []
for subject, predicate in examples:
    value = g.value(subject, predicate)
    datatype = value.datatype.fragment if value.datatype else "string"  # no datatype = text
    python_value = value.toPython()
    literals.append((subject.fragment, predicate.fragment, str(value), datatype, python_value))

# 3. Language tags: one property, the same word in two languages
specialty = sorted((str(word), word.language) for word in g.objects(BB.BurgerBarn, BB.specialty))

# 4. Why datatypes matter. Both fryers are set to 175 C, so "above 300" should find none.
#    Fryer_1's 175 is a number. Fryer_2's "175" is text (in quotes), which is not compared
#    as a number: rdflib lets it through. A wrong answer, and no error!
hot_query = "SELECT ?fryer WHERE { ?fryer bb:oilSetpointC ?temp . FILTER(?temp > 300) }"
hot_fryers = sorted(row.fryer.fragment for row in g.query(hot_query))
#    isNumeric() asks "is this literal a number?": the way to find the bad one
text_query = "SELECT ?fryer WHERE { ?fryer bb:oilSetpointC ?temp . FILTER(!isNumeric(?temp)) }"
text_setpoints = sorted(row.fryer.fragment for row in g.query(text_query))

print("Literals (thing, property, text, datatype, Python value):")
for row in literals:
    print(f"  {row[0]:16} {row[1]:14} {row[2]:20} {row[3]:9} {row[4]!r}")
print("\nSpecialty, with language tags:", specialty)
print("Fryers with a setpoint above 300 C:", hot_fryers, "<- wrong: both are set to 175")
print("Fryers whose setpoint is text, not a number:", text_setpoints)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "datatypes": [(row[0], row[1], row[3]) for row in literals],
    "specialty": specialty,
    "hot_fryers": hot_fryers,
    "text_setpoints": text_setpoints,
}
