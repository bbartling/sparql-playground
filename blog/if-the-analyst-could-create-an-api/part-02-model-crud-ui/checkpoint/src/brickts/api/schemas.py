from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Same text as scripts/sparql/02_fc1_points.rq (Swagger example twin)
FC1_POINTS_QUERY = """\
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>

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
"""


class SparqlRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"query": FC1_POINTS_QUERY},
        }
    )

    query: str = Field(
        min_length=1,
        description="Read-only SPARQL SELECT/ASK (no UPDATE/LOAD/SERVICE/FROM).",
        examples=[FC1_POINTS_QUERY],
    )


class HealthResponse(BaseModel):
    status: str = "ok"
    ready: bool = True
    bootstrap_error: str | None = None


class TimeseriesOut(BaseModel):
    point_id: str
    timeseries_id: str
    samples: list[dict]
    truncated: bool
