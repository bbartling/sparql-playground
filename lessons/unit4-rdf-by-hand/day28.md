# Day 28 — Literals and XSD datatypes: when "175" is not 175

**Goal:** see what type each value (literal) has, meet the common XSD datatypes, and watch a number written in
quotes give a wrong answer without any error.

## Read

Yesterday's labels were **literals**: values, not things. Every literal has a **datatype**, borrowed from XML Schema
(prefix `xsd:`). Turtle picks one for you when you write a bare value, and you can name one with `^^`:

| You write | Datatype | Python value (rdflib) | Burger Barn example |
|---|---|---|---|
| `"degC"` | `xsd:string` (text, the default) | `str` | a sensor's unit |
| `40` | `xsd:integer` (whole number) | `int` | seats |
| `3.0` or `"3.0"^^xsd:decimal` | `xsd:decimal` (exact decimal) | `Decimal` | cooler setpoint |
| `true` | `xsd:boolean` | `bool` | is open |
| `"2019-05-04"^^xsd:date` | `xsd:date` (a day) | `date` | opened on |
| `"2026-10-01T09:30:00"^^xsd:dateTime` | `xsd:dateTime` (day and time) | `datetime` | last inspected |
| `"10:30:00"^^xsd:time` | `xsd:time` (time of day) | `time` | opens at |
| `"PT3M"^^xsd:duration` | `xsd:duration` (how long) | `timedelta` | fry basket timer |
| `"fries"@en`, `"frites"@fr` | a string with a **language tag** | `str` | specialty |

`PT3M` reads "a Period of Time, 3 Minutes". `P1DT2H` would be one day and two hours.

Now the trap. Fryer_1's setpoint is `175.0`, a number. Fryer_2's is `"175"`, **in quotes**: text that happens to
look like a number. [`day28_rdf.py`](day28_rdf.py) prints every literal with its datatype, then asks SPARQL "which
fryers are set above 300 °C?" with `FILTER(?temp > 300)`. Neither is, so the right answer is *none*.

## Run

```bash
uv run python lessons/course.py run 28
```

```
Literals (thing, property, text, datatype, Python value):
  Fryer_1_OilTemp  unit           degC                 string    'degC'
  BurgerBarn       seats          40                   integer   40
  WalkInCooler_1   airSetpointC   3.0                  decimal   Decimal('3.0')
  BurgerBarn       isOpen         true                 boolean   True
  BurgerBarn       openedOn       2019-05-04           date      datetime.date(2019, 5, 4)
  Fryer_1          lastInspected  2026-10-01T09:30:00  dateTime  datetime.datetime(2026, 10, 1, 9, 30)
  BurgerBarn       opensAt        10:30:00             time      datetime.time(10, 30)
  Fryer_1          fryTime        PT3M                 duration  datetime.timedelta(seconds=180)
  Fryer_1          oilSetpointC   175.0                decimal   Decimal('175.0')
  Fryer_2          oilSetpointC   175                  string    '175'

Specialty, with language tags: [('fries', 'en'), ('frites', 'fr')]
Fryers with a setpoint above 300 C: ['Fryer_2'] <- wrong: both are set to 175
Fryers whose setpoint is text, not a number: ['Fryer_2']
```

The query says Fryer_2 is above 300. It isn't. Comparing text with a number has no sensible answer, and rdflib
quietly lets the text through. (Other SPARQL engines may drop it instead. Either way the answer is silently
wrong.) `isNumeric(?temp)` is the honest test: it finds the setpoint that is text. Day 35 adds a SHACL rule,
`sh:datatype xsd:decimal`, that rejects it outright, and the ontology (Day 32) says the range of `oilSetpointC` is
`xsd:decimal`.

## How this maps to buildings

> **Buildings box.** BAS exports are full of numbers stored as text ("72.5", "ON", "1"). **Brick** stores values
> with explicit datatypes (a setpoint's value is an `xsd:decimal`, a timestamp an `xsd:dateTime`); **ASHRAE 223P**
> does the same for its property values; **Haystack** has its own kinds (`Number` with a unit, `Bool`, `Date`,
> `Time`, `DateTime`) that map onto these XSD types when exported to RDF. A setpoint saved as text breaks every
> "above / below" fault rule, exactly like Fryer_2.

## Why it matters

A literal's datatype decides how it compares, sorts and adds up. Write numbers as numbers, dates as dates, and
check the ones you didn't write yourself.

## Try it

1. Change Fryer_2's setpoint to `175.0` (no quotes) and re-run. What do the last two lines print?
2. What datatype does `"2026-10-01"` (no `^^`) have?
3. **Mini challenge (Burger Barn):** how many seconds does Fryer_1's basket timer run? Get it from Python,
   not by doing the math in your head.

<details><summary>Answers</summary>

1. Both lists are empty: nothing is above 300, and no setpoint is text.
2. `xsd:string`. Without `^^xsd:date` it is just text that looks like a date.
3. **180.** `g.value(BB.Fryer_1, BB.fryTime).toPython()` is a `timedelta`, and `.total_seconds()` gives `180.0`.
   (The course's tests check this answer.)

</details>
