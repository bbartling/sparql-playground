from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from rdflib import BNode, Literal
from rdflib.namespace import RDFS

from brickts.api.deps import AppState, get_app_state
from brickts.graph.namespaces import BLDG, BRICK, RDF, REF, UNIT
from brickts.graph.validate import run_shacl, run_sparql_checks

router = APIRouter(prefix="/api/model", tags=["model"])


class PointMutation(BaseModel):
    point_id: str = Field(min_length=1, max_length=128)
    label: str
    brick_class: str
    owner_id: str
    timeseries_id: str
    unit: str | None = None


class PointsMutation(BaseModel):
    points: list[PointMutation]


def _require_mutations(state: AppState) -> None:
    if not state.settings.allow_mutations:
        raise HTTPException(status_code=403, detail="mutations disabled")


@router.get("/validate")
def validate_model(
    shacl: bool = Query(default=False),
    state: AppState = Depends(get_app_state),
):
    issues = run_sparql_checks(state.graph.state.model, state.graph.ontology)
    shacl_ok, shacl_report = (True, "")
    if shacl:
        shacl_ok, shacl_report = run_shacl(state.graph.state.model, state.graph.ontology)
    return {
        "checks": [i.__dict__ for i in issues],
        "shacl_conforms": shacl_ok,
        "shacl_report": shacl_report[:4000] if shacl_report else "",
    }


@router.get("/ttl")
def download_ttl(state: AppState = Depends(get_app_state)):
    text = state.graph.state.model.serialize(format="turtle")
    return PlainTextResponse(text, media_type="text/turtle")


@router.post("/points")
def add_points(body: PointsMutation, state: AppState = Depends(get_app_state)):
    _require_mutations(state)
    db = BLDG["timeseries_db"]
    triples: list[tuple] = []
    for p in body.points:
        pi = BLDG[p.point_id]
        oi = BLDG[p.owner_id]
        triples.append((pi, RDF.type, BRICK[p.brick_class]))
        triples.append((pi, RDFS.label, Literal(p.label)))
        triples.append((pi, BRICK.isPointOf, oi))
        triples.append((oi, BRICK.hasPoint, pi))
        if p.unit:
            triples.append((pi, BRICK.hasUnit, UNIT[p.unit]))
        ref = BNode()
        triples.append((pi, REF.hasExternalReference, ref))
        triples.append((ref, RDF.type, REF.TimeseriesReference))
        triples.append((ref, REF.hasTimeseriesId, Literal(p.timeseries_id)))
        triples.append((ref, REF.storedAt, db))
    try:
        state.graph.add_triples(triples)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if state.settings.serialize_on_mutation:
        state.graph.serialize_atomic()
    return {"added": len(body.points)}


@router.post("/flush")
def flush_model(state: AppState = Depends(get_app_state)):
    _require_mutations(state)
    state.graph.serialize_atomic()
    return {"flushed": True}
