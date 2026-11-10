# Day 40 — Reuse, part two: aligning your terms with Brick

**Goal:** link the burger terms to Brick with the right strength of link, so a Brick-only query finds burger
equipment too, and know when *not* to link.

## Read

Day 36 found four burger terms that Brick already has. Instead of deleting ours, we **align** them: a separate file,
[`burger_alignment.ttl`](burger_alignment.ttl), says how each relates to Brick. Choose the **weakest link that is
true**:

| Link | Means | Logic for a reasoner | Burger example |
|---|---|---|---|
| `rdfs:subClassOf` | every X is a Y (not the other way) | yes | `burger:Equipment rdfs:subClassOf brick:Equipment` |
| `rdfs:subPropertyOf` | every use of p is a use of q | yes | `burger:hasPoint rdfs:subPropertyOf brick:hasPoint` |
| `owl:equivalentClass` | X and Y mean exactly the same | yes, merges members | `burger:TemperatureSensor` and `brick:Temperature_Sensor` |
| `skos:exactMatch` | same meaning, said for people and search tools | none | the same pair |
| `skos:closeMatch` | similar, **not** the same | none | `burger:Restaurant` and `brick:Building` |

Why not make a restaurant `equivalentClass` building? Because a food-court burger stand is a restaurant but not a
building. Claim too much and every reasoner downstream draws wrong conclusions. `skos:closeMatch` points readers to
the similar term and lets no software conclude anything.

This is exactly how **Brick's own guide to extensions**
([Extending Brick](https://docs.brickschema.org/extra/extending.html)) says to do it: put your terms in your own
namespace, give each `a owl:Class`, a `skos:definition` and an `rdfs:subClassOf` link to the nearest Brick class,
and use `rdfs:subPropertyOf` for relationships that specialize Brick's. (Its example extension even has an ice
machine.)

[`day40_rdf.py`](day40_rdf.py) loads the tiny Brick building, the burger ontology, the restaurant and the
alignment, then asks four **Brick-only** questions, with no reasoner and then with one.

## Run

```bash
uv run python lessons/course.py run 40
```

```
brick:Equipment
   no reasoner: ['AHU_1', 'Cooler_1', 'Fryer_1', 'Fryer_2', 'Grill_1', 'VAV_1', 'VAV_2']
   reasoner:    ['AHU_1', 'Cooler_1', 'Fryer_1', 'Fryer_2', 'Grill_1', 'VAV_1', 'VAV_2']
brick:Temperature_Sensor
   no reasoner: ['AHU_1_SAT', 'VAV_1_ZoneTemp']
   reasoner:    ['AHU_1_SAT', 'Fryer_1_OilTemp', 'Fryer_2_OilTemp', 'Grill_1_SurfaceTemp', 'VAV_1_ZoneTemp']
brick:hasPoint
   no reasoner: ['AHU_1', 'Fryer_1', 'Fryer_2', 'Grill_1', 'VAV_1', 'VAV_2']
   reasoner:    ['AHU_1', 'Fryer_1', 'Fryer_2', 'Grill_1', 'VAV_1', 'VAV_2']
brick:Building
   no reasoner: ['Building_1']
   reasoner:    ['Building_1']
```

One query, `?x a/rdfs:subClassOf* brick:Equipment`, now finds the AHU, the VAVs **and** the fryers, grill and
cooler, through `rdfs:subClassOf`. The temperature sensors need the reasoner, because a `subClassOf*` path doesn't
follow `owl:equivalentClass`. And `brick:Building` stays just `Building_1`: closeMatch carries no logic, as
intended.

## How this maps to buildings

> **Buildings box.** This is the everyday job of building ontology work: a vendor's or site's own terms aligned
> to **Brick** (and often to **ASHRAE 223P** and **Haystack**), so standard queries and FDD rules work on them. A
> site-specific "Kitchen Exhaust Hood" becomes `rdfs:subClassOf brick:Equipment` (or a more specific Brick class);
> a Haystack-tagged point gets an `skos:exactMatch` or a class from the Haystack-to-Brick mapping.

## Why it matters

Alignment is what makes your ontology useful to tools you didn't write. Strong links you can't defend are worse
than none, so pick the weakest true one.

## Try it

1. Change `skos:closeMatch` to `owl:equivalentClass` for Restaurant/Building and re-run. What does `brick:Building`
   return now, and why is that a problem?
2. Which Brick class might `burger:WalkInCooler` sit under? (Look it up in the Brick docs.)
3. **Mini challenge (Burger Barn):** delete the `owl:equivalentClass` line (keep the `skos:exactMatch`) and run
   the reasoner. Which `brick:Temperature_Sensor`s are left?

<details><summary>Answers</summary>

1. It adds `Restaurant_1`. Now every "for each building" FDD rule thinks the burger restaurant is a building.
2. A good fit is `brick:Equipment` (or a more specific refrigeration class if your Brick version has one).
   Choose the nearest class that is truly a parent.
3. Only **AHU_1_SAT** and **VAV_1_ZoneTemp**: `skos:exactMatch` carries no logic, so the burger sensors stay out.
   (The course's tests check this answer.)

</details>
