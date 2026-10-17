"""Haystack model tree + CRUD + markers (gated by BLDGTS_ALLOW_MUTATIONS)."""

from __future__ import annotations

from typing import Any

from bldgts.api.deps import AppState, get_app_state
from bldgts.haystack.defs import catalog_for_level
from bldgts.haystack.suggest import guess_marker_bundle, suggest_markers
from bldgts.services import model_crud as crud
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/model", tags=["model-crud"])


class EquipBody(BaseModel):
    equipment_id: str = Field(min_length=1, max_length=128)
    label: str | None = None
    kind: str = "ahu"
    parent_id: str | None = "Building_50"
    expected_revision: int | None = None


class PointBody(BaseModel):
    point_id: str = Field(min_length=1, max_length=128)
    owner_id: str = Field(min_length=1, max_length=128)
    label: str | None = None
    brick_class: str = "Sensor"
    timeseries_id: str | None = None
    expected_revision: int | None = None


class HideBody(BaseModel):
    entity_id: str = Field(min_length=1, max_length=128)
    expected_revision: int | None = None


class MarkerUpdate(BaseModel):
    entity_id: str = Field(min_length=1, max_length=128)
    markers: list[str] = Field(min_length=1)
    level: str | None = None


class TagsBody(BaseModel):
    updates: list[MarkerUpdate] = Field(min_length=1)
    expected_revision: int | None = None


class RenameBody(BaseModel):
    entity_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    expected_revision: int | None = None


def _result(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("conflict"):
        raise HTTPException(status_code=409, detail=payload)
    if payload.get("ok") is False:
        raise HTTPException(status_code=400, detail=payload)
    return payload


def _map_level(node_type: str) -> str:
    if node_type == "equipment":
        return "equip"
    return node_type


@router.get("/tree", summary="Site → building → equipment → point tree")
def get_tree(state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    return {
        "ok": True,
        "revision": state.graph.revision,
        "allow_mutations": state.settings.allow_mutations,
        "tree": crud.build_tree(state.graph),
    }


@router.get("/haystack/catalog", summary="Haystack markers allowed for a tree level")
def haystack_catalog(level: str = Query(default="point")) -> dict[str, Any]:
    try:
        catalog = catalog_for_level(_map_level(level))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "level": level, "catalog": catalog}


@router.get("/haystack/suggest", summary="Closest Haystack markers for a name")
def haystack_suggest(
    q: str = Query(min_length=1),
    level: str = Query(default="point"),
    n: int = Query(default=8, ge=1, le=25),
) -> dict[str, Any]:
    try:
        hits = suggest_markers(q, _map_level(level), n=n)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "query": q, "level": level, "suggestions": hits}


@router.get(
    "/haystack/guess",
    summary="One-shot FinStack/Niagara-style marker bundle for a name",
)
def haystack_guess(
    q: str = Query(min_length=1),
    level: str = Query(default="point"),
) -> dict[str, Any]:
    try:
        bundle = guess_marker_bundle(q, _map_level(level))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **bundle}


@router.get("/dashboard", summary="Haystack marker coverage across points")
def dashboard(state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    return {"ok": True, **crud.dashboard(state.graph)}


@router.post("/equip", summary="Add or update equipment (mutations flag required)")
def upsert_equip(body: EquipBody, state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    try:
        return _result(
            crud.upsert_equipment(
                state.graph,
                equipment_id=body.equipment_id,
                label=body.label,
                kind=body.kind,
                parent_id=body.parent_id,
                expected_revision=body.expected_revision,
                allow_mutations=state.settings.allow_mutations,
            )
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/point", summary="Add or update a point; keeps existing timeseries refs")
def upsert_point(body: PointBody, state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    try:
        return _result(
            crud.upsert_point(
                state.graph,
                point_id=body.point_id,
                label=body.label,
                owner_id=body.owner_id,
                brick_class=body.brick_class,
                timeseries_id=body.timeseries_id,
                expected_revision=body.expected_revision,
                allow_mutations=state.settings.allow_mutations,
            )
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/hide", summary="Soft-delete (hide) without dropping timeseries refs")
def hide_entity(body: HideBody, state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    try:
        return _result(
            crud.hide_entity(
                state.graph,
                entity_id=body.entity_id,
                expected_revision=body.expected_revision,
                allow_mutations=state.settings.allow_mutations,
            )
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/tags", summary="Batch Haystack markers on tree entities")
def apply_tags(body: TagsBody, state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    try:
        return _result(
            crud.apply_markers(
                state.graph,
                updates=[u.model_dump(exclude_none=True) for u in body.updates],
                expected_revision=body.expected_revision,
                allow_mutations=state.settings.allow_mutations,
            )
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/rename", summary="Rename a tree entity (rdfs:label)")
def rename(body: RenameBody, state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    try:
        return _result(
            crud.rename_entity(
                state.graph,
                entity_id=body.entity_id,
                label=body.label,
                expected_revision=body.expected_revision,
                allow_mutations=state.settings.allow_mutations,
            )
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/flush", summary="Write building.ttl now (also runs on a background thread)")
def flush_ttl(state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    state.graph.serialize_atomic()
    return {
        "ok": True,
        "revision": state.graph.revision,
        "tutorial_ttl": str(state.settings.tutorial_ttl_path),
        "snapshot": str(state.settings.snapshot_path),
    }
