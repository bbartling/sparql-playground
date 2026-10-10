# SPARQL queries to try

Paste these into Swagger → **POST** `/api/sparql`  
(live: <https://sparql-playground.onrender.com/docs>).

Every query needs the prefixes below (copy them with the query).

This demo site models **AHUs + zones**. Empty results for boilers/chillers/etc. mean that class is not in the graph yet — that is expected.

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:   <http://www.w3.org/2002/07/owl#>
PREFIX ref:   <https://brickschema.org/schema/Brick/ref#>
PREFIX tag:   <https://brickschema.org/schema/BrickTag#>
PREFIX bts:   <https://example.org/openfdd/brickts#>
```

---

## 1. Count equipment by kind

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:   <http://www.w3.org/2002/07/owl#>

SELECT ?kind (COUNT(DISTINCT ?equip) AS ?n) WHERE {
  VALUES ?kind {
    brick:Air_Handler_Unit
    brick:Variable_Air_Volume_Box
    brick:Boiler
    brick:Chiller
    brick:HVAC_Zone
  }
  ?equip a/(rdfs:subClassOf|owl:equivalentClass)* ?kind .
  FILTER(STRSTARTS(STR(?equip), STR(bldg:)))
}
GROUP BY ?kind
ORDER BY DESC(?n) ?kind
```

---

## 2. List AHUs

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:   <http://www.w3.org/2002/07/owl#>

SELECT ?ahu ?label WHERE {
  ?ahu a/(rdfs:subClassOf|owl:equivalentClass)* brick:Air_Handler_Unit .
  FILTER(STRSTARTS(STR(?ahu), STR(bldg:)))
  OPTIONAL { ?ahu rdfs:label ?label }
}
ORDER BY ?ahu
```

---

## 3. Parts of AHU_1 (fan, damper, …)

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?part ?partType ?label WHERE {
  bldg:AHU_1 brick:hasPart ?part .
  ?part a ?partType .
  FILTER(STRSTARTS(STR(?partType), STR(brick:)))
  OPTIONAL { ?part rdfs:label ?label }
}
ORDER BY ?part
```

---

## 4. Zones fed by AHU_1

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?zone ?label WHERE {
  bldg:AHU_1 brick:feeds ?zone .
  ?zone a brick:HVAC_Zone .
  OPTIONAL { ?zone rdfs:label ?label }
}
ORDER BY ?zone
```

---

## 5. Points on AHUs + timeseries ids

This is the Brick → historian link (`ref:hasTimeseriesId`).

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:   <http://www.w3.org/2002/07/owl#>
PREFIX ref:   <https://brickschema.org/schema/Brick/ref#>

SELECT ?ahu ?point ?label ?cls ?timeseriesId WHERE {
  ?ahu a/(rdfs:subClassOf|owl:equivalentClass)* brick:Air_Handler_Unit .
  FILTER(STRSTARTS(STR(?ahu), STR(bldg:)))
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?ahu .
  OPTIONAL { ?point rdfs:label ?label }
  OPTIONAL {
    ?point a ?cls .
    FILTER(STRSTARTS(STR(?cls), STR(brick:)))
  }
  OPTIONAL {
    ?point ref:hasExternalReference ?ref .
    ?ref ref:hasTimeseriesId ?timeseriesId .
  }
}
ORDER BY ?ahu ?point
```

---

## 6. Find duct static setpoint by Brick tags

Tags live on the Brick *class* in the ontology.

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX tag:   <https://brickschema.org/schema/BrickTag#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?point ?label WHERE {
  ?point a ?cls .
  ?cls brick:hasAssociatedTag tag:Supply , tag:Air , tag:Static , tag:Pressure , tag:Setpoint .
  FILTER(STRSTARTS(STR(?point), STR(bldg:)))
  OPTIONAL { ?point rdfs:label ?label }
}
```

---

## 7. FC1 points on AHU_1 (sensor, setpoint, fan speed)

Same idea as `scripts/lesson_02_fc1_points.py`.

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:   <http://www.w3.org/2002/07/owl#>
PREFIX ref:   <https://brickschema.org/schema/Brick/ref#>

SELECT ?role ?brickClass ?point ?timeseriesId WHERE {
  BIND(bldg:AHU_1 AS ?ahu)
  VALUES (?role ?brickClass ?needSupplyFan) {
    ("duct-static-pressure"    brick:Supply_Air_Static_Pressure_Sensor  false)
    ("duct-static-pressure-sp" brick:Supply_Air_Static_Pressure_Setpoint false)
    ("fan-cmd"                 brick:Fan_Speed_Command                   true)
  }
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?ahu .
  ?point a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?brickClass .
  OPTIONAL {
    ?owner a/(rdfs:subClassOf|owl:equivalentClass)* brick:Supply_Fan .
    BIND(true AS ?onSupplyFan)
  }
  FILTER(!?needSupplyFan || BOUND(?onSupplyFan))
  OPTIONAL {
    ?point ref:hasExternalReference ?ref .
    ?ref ref:hasTimeseriesId ?timeseriesId .
  }
}
ORDER BY ?role
```

After you have a `point` local name (e.g. `AHU_1_DA_P`), fetch samples with  
**GET** `/api/points/AHU_1_DA_P/timeseries?limit=100`.

---

## 8. Where is the timeseries database?

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX ref:   <https://brickschema.org/schema/Brick/ref#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX bts:   <https://example.org/openfdd/brickts#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?db ?label ?backend WHERE {
  { ?db a ref:Database } UNION { ?db a brick:Database }
  FILTER(STRSTARTS(STR(?db), STR(bldg:)))
  OPTIONAL { ?db rdfs:label ?label }
  OPTIONAL { ?db bts:backend ?backend }
}
```

---

## 9. Points missing a timeseries ref (should be empty)

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg:  <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:   <http://www.w3.org/2002/07/owl#>
PREFIX ref:   <https://brickschema.org/schema/Brick/ref#>

SELECT ?point ?label WHERE {
  ?point a/(rdfs:subClassOf|owl:equivalentClass)* brick:Point .
  FILTER(STRSTARTS(STR(?point), STR(bldg:)))
  FILTER NOT EXISTS { ?point ref:hasExternalReference ?ref }
  OPTIONAL { ?point rdfs:label ?label }
}
ORDER BY ?point
```

---

## More presets

Machine-readable copies of many queries live under `src/brickts/sparql/examples/*.rq`.  
In Swagger, **GET** `/api/sparql/examples` returns them all as JSON — copy any `query` into **POST** `/api/sparql`.
