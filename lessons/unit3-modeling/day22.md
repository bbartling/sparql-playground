# Day 22 — Haystack tags as RDF: find a rule's inputs by tags with SPARQL

**Goal:** read one point's Haystack tags in `model/building_50.ttl`, then find FC1's three inputs for every AHU by
asking for tags, in SPARQL (rdflib, pandas side) and in a flat SQL table (SQL side), and see what the graph holds
that the table doesn't.

## Read

**Project Haystack** describes equipment and points with **tags**. A **marker** tag is just a name (`point`,
`sensor`, `pressure`, `his`); a **valued** tag has a value (`unit` = `inH2O`, `kind` = `Number`). Two valued tags are
**refs**, pointers to other entities: `equipRef` ("this point belongs to that equipment") and `siteRef`. Tags are how
people in the industry describe buildings, and this repo writes them as RDF, in its own `bts:` vocabulary, so a graph
database can query them. One point, `bldg:AHU_1_DA_P`, in Turtle:

```turtle
bldg:AHU_1_DA_P a bts:Entity ;
    rdfs:label "AHU1 DA-P" ;
    ref:hasExternalReference [ ... ] ;                      # where its history lives (Day 24)
    bts:hasHaystackMarker "air", "discharge", "his", "point", "pressure", "sensor" ;
    bts:hasHaystackTag [ bts:tagName "equipRef" ; bts:tagValue bldg:AHU_1 ],
                       [ bts:tagName "unit" ;     bts:tagValue "inH2O" ],
                       [ bts:tagName "ofddRole" ; bts:tagValue "duct-static-pressure" ], ... .
```

Markers are one predicate with many values. Valued tags are small nodes with a `tagName` and a `tagValue`. `ofddRole`
is this repo's tag for the Open-FDD role: the same role names as Day 21's map, now stored *in the model*, on the
point. `equipRef`'s value is a node (`bldg:AHU_1`), not a string, so the graph can follow it.

**Finding FC1's inputs.** FC1 needs the fan status, duct static pressure and its setpoint, for each AHU. In SPARQL
that is a pattern of tags with a `FILTER` on the role:

```sparql
SELECT ?equip ?role ?point ?timeseries_id WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseries_id .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue ?equip .
}
```

**Pattern order matters.** rdflib evaluates triple patterns roughly top to bottom. The first pattern starts from the
118 points that have a timeseries reference, so every join after it is small. Start with "every node that has an
`ofddRole` tag" and rdflib builds a large intermediate result first; against the API that hit its 10 s limit. A
database planner reorders joins for you; a simple engine does not, so put the most selective pattern first.

**The flat shadow.** The model was built from `model/points/*.csv`, one row per point (point id, equipment, role,
source column, UUID, ...). The SQL script loads those rows into a `TEMP` table `point` and asks the same question as a
plain `WHERE openfdd_role IN (...)`. The same three points per AHU come
back. The SQL version is *simpler*. So why have a graph?

| | flat table `point` | RDF graph |
|---|---|---|
| a point's role | a column, `openfdd_role` | a tag: `ofddRole` |
| which equipment | a column, derived here from the *file name* | a tag, `equipRef`, pointing at an entity |
| markers (`sensor`, `pressure`, ...) | none: the CSV never had them | a first-class predicate |
| hierarchy (point → equipment → site) | one `owner_id` column, one level | refs you can follow to any depth |
| where the history lives | one column `timeseries_id`, one store | any number of references, each with its own store (Day 24) |
| a new kind of fact | `ALTER TABLE` | add a triple |

The table is a **flat shadow**: it answers today's question fast, but it only contains what was flattened into it.
The graph keeps the structure.

| Step | `day22_pandas.py` (rdflib) | `day22_sql.py` (SQLite) |
|---|---|---|
| load | `Graph().parse("building_50.ttl")` (4,147 triples) | `INSERT` 118 CSV rows into `TEMP TABLE point` |
| FC1's inputs | SPARQL `FILTER(?role IN ...)` | `WHERE openfdd_role IN (...)` |
| per-AHU count | `GROUP BY ?equip` | `GROUP BY equipment_id` |

## Run

```bash
uv run python lessons/course.py run 22
```

That runs [`day22_pandas.py`](day22_pandas.py), then [`day22_sql.py`](day22_sql.py). No server is involved: rdflib
reads the Turtle file straight into memory. Both end with the same six rows (the pandas script also prints one
point's markers and tags, which the table doesn't have):

```
equipment_id                    role        point_id                        timeseries_id
       AHU_1    duct-static-pressure      AHU_1_DA_P 52422584-9894-50bd-9696-2fbb8b062518
       AHU_1 duct-static-pressure-sp   AHU_1_DA_P_SP 761c2b61-4982-5157-bc66-2010cf6e2a47
       AHU_1              fan-status AHU_1_SF_Status 9ebf80dd-7821-510b-b2c0-cd0151e093c9
       AHU_2    ...
```

Nothing in either script names a column. The two are compared on `(equipment, role, point id)` plus the UUID, and on
the number of role-tagged points per AHU (13 each).

## Try it

1. Find the AHUs' **discharge air temperature** and its setpoint (`discharge-air-temp`, `discharge-air-temp-sp`) in
   both scripts. How many lines change?
2. In the pandas script, query by *marker* instead of role: which points have the markers `pressure` **and** `sp`?
   Can the SQL table answer that?

<details><summary>Answers</summary>

1. Only the role strings in the filter (`FILTER(?role IN (...))` and `WHERE openfdd_role IN (...)`).
2. Two marker values on the same point: `?p bts:hasHaystackMarker "pressure", "sp" .` (the comma repeats the same
   subject and predicate). The flat table cannot: the CSVs have no markers. You could add a `markers` column, but then
   "has marker X" is a string search, where the graph has it as data.

</details>

## Why it matters

Rules that ask for roles survive a change of building, as long as the building's model has the tags. That is why
Haystack tagging is worth the effort in industry. Note what is still missing: the answer is a UUID, an opaque string
you can't read. Tomorrow we look at where it comes from and at the table that stores history under it.
