from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from open_fdd.rules import RULES, run_rule
from rdflib import Graph

from brickts.services.faults import ROLE_REQUIREMENTS, list_faults
from brickts.services.points import find_points
from brickts.services.timeseries import read_point_timeseries
from brickts.store.base import TimeseriesStore


@dataclass
class RoleBinding:
    role: str
    point_id: str
    timeseries_id: str | None
    brick_class: str
    owner_id: str


@dataclass
class RuleRunResult:
    rule_id: str
    equipment_id: str
    status: str
    fault_hours: float | None
    fault_pct: float | None
    sample_count: int | None
    fault_sample_count: int | None
    bindings: list[RoleBinding]
    evidence: dict


def _rule_by_id(rule_id: str):
    for rule in RULES:
        if rule.id == rule_id:
            return rule
    return None


def resolve_role_bindings(union: Graph, equipment_id: str, roles: list[str]) -> list[RoleBinding]:
    bindings: list[RoleBinding] = []
    for role in roles:
        req = ROLE_REQUIREMENTS.get(role)
        if req is None:
            raise ValueError(f"no Brick mapping for role {role}")
        brick_class, owner_class = req
        pts = find_points(
            union,
            equipment_id,
            brick_class=brick_class,
            parent_class=owner_class,
            include_subclasses=True,
        )
        if len(pts) != 1:
            raise ValueError(f"expected 1 point for role {role}, got {len(pts)}")
        p = pts[0]
        bindings.append(
            RoleBinding(
                role=role,
                point_id=p.point_id,
                timeseries_id=p.timeseries_id,
                brick_class=p.brick_class,
                owner_id=p.owner_id,
            )
        )
    return bindings


def role_lesson_query(equipment_id: str, role: str) -> str:
    req = ROLE_REQUIREMENTS.get(role)
    if req is None:
        raise ValueError(f"no Brick mapping for role {role}")
    brick_class, owner_class = req
    if owner_class:
        return f"""PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>

SELECT ?point ?label ?cls ?owner ?timeseriesId WHERE {{
  BIND(bldg:{equipment_id} AS ?equip)
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?equip .
  ?point a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* brick:{brick_class} .
  ?owner a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* brick:{owner_class} .
  OPTIONAL {{ ?point rdfs:label ?label }}
  OPTIONAL {{ ?point a ?cls . FILTER(STRSTARTS(STR(?cls), STR(brick:))) }}
  OPTIONAL {{
    ?point ref:hasExternalReference ?ref .
    ?ref ref:hasTimeseriesId ?timeseriesId .
  }}
}}
"""
    return f"""PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>

SELECT ?point ?label ?cls ?owner ?timeseriesId WHERE {{
  BIND(bldg:{equipment_id} AS ?equip)
  ?point (brick:isPointOf|^brick:hasPoint) ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?equip .
  ?point a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* brick:{brick_class} .
  OPTIONAL {{ ?point rdfs:label ?label }}
  OPTIONAL {{ ?point a ?cls . FILTER(STRSTARTS(STR(?cls), STR(brick:))) }}
  OPTIONAL {{
    ?point ref:hasExternalReference ?ref .
    ?ref ref:hasTimeseriesId ?timeseriesId .
  }}
}}
"""


async def run_equipment_rule(
    union: Graph,
    stores: dict[str, TimeseriesStore],
    *,
    equipment_id: str,
    rule_id: str,
    poll_seconds: int = 300,
    limit: int | None = None,
) -> RuleRunResult:
    rule = _rule_by_id(rule_id)
    if rule is None:
        raise ValueError(f"unknown rule {rule_id}")
    rows = list_faults(union, equipment_id, include_generic=True)
    match = next((r for r in rows if r.rule_id == rule_id), None)
    if match is None:
        raise ValueError(f"rule {rule_id} not listed for {equipment_id}")
    if not match.applicable:
        raise ValueError(f"rule {rule_id} not applicable: {match.reason}")

    required = list(getattr(rule, "required_roles", ()) or ())
    if not required:
        raise ValueError(f"rule {rule_id} has no required roles (sensor sweep); use open-fdd CLI")

    bindings = resolve_role_bindings(union, equipment_id, required)
    series: dict[str, pd.Series] = {}
    for b in bindings:
        payload = await read_point_timeseries(
            union,
            stores,
            b.point_id,
            start=None,
            end=None,
            limit=limit,
            max_rows=limit or 200_000,
        )
        samples = payload.samples
        idx = pd.to_datetime([s["ts"] for s in samples], unit="s", utc=True)
        series[b.role] = pd.Series([s["value"] for s in samples], index=idx, name=b.role)
    df = pd.DataFrame(series).sort_index()
    df.attrs.update(equipment_id=equipment_id, equipment_type="ahu")
    res = run_rule(rule_id, df, poll_seconds=poll_seconds)
    payload = res.to_dict() if hasattr(res, "to_dict") else {}
    return RuleRunResult(
        rule_id=rule_id,
        equipment_id=equipment_id,
        status=str(getattr(res, "status", "")),
        fault_hours=getattr(res, "fault_hours", None),
        fault_pct=getattr(res, "fault_pct", None),
        sample_count=getattr(res, "sample_count", None),
        fault_sample_count=getattr(res, "fault_sample_count", None),
        bindings=bindings,
        evidence=payload.get("evidence", {}) if isinstance(payload, dict) else {},
    )
