from __future__ import annotations

from pydantic import BaseModel, Field

_MECH_SUMMARY_EXAMPLE = """\
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

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
"""


class SparqlRequest(BaseModel):
    query: str = Field(
        min_length=1,
        description="Read-only SPARQL SELECT/ASK (no UPDATE/LOAD/SERVICE/FROM).",
        examples=[_MECH_SUMMARY_EXAMPLE],
    )


class HealthResponse(BaseModel):
    status: str = "ok"
    ready: bool = True
    bootstrap_error: str | None = None


class RoleBindingOut(BaseModel):
    role: str
    point_id: str
    timeseries_id: str | None = None
    brick_class: str
    owner_id: str


class RuleRunOut(BaseModel):
    rule_id: str
    equipment_id: str
    status: str
    fault_hours: float | None = None
    fault_pct: float | None = None
    sample_count: int | None = None
    fault_sample_count: int | None = None
    bindings: list[RoleBindingOut]
    evidence: dict = Field(default_factory=dict)


class PointOut(BaseModel):
    point_id: str
    label: str
    brick_class: str
    owner_id: str
    timeseries_id: str | None = None
    unit: str | None = None


class TimeseriesOut(BaseModel):
    point_id: str
    timeseries_id: str
    samples: list[dict]
    truncated: bool


class FaultOut(BaseModel):
    rule_id: str
    title: str
    applicable: bool
    generic: bool
    reason: str


class TimeseriesQueryItem(BaseModel):
    point_id: str
    start: int | None = None
    end: int | None = None
    limit: int | None = None


class TimeseriesBatchRequest(BaseModel):
    queries: list[TimeseriesQueryItem]
