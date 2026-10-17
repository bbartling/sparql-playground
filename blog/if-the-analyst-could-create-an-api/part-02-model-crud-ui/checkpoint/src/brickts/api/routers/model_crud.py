"""Brick model tree + CRUD + ops tags (gated by BRICKTS_ALLOW_MUTATIONS)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from brickts.api.deps import AppState, get_app_state
from brickts.services import model_crud as crud

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


class TagUpdate(BaseModel):
    point_id: str = Field(min_length=1, max_length=128)
    status: Literal["received", "not_received"] | None = None
    meta: str | None = None
    note: str | None = None


class TagsBody(BaseModel):
    updates: list[TagUpdate] = Field(min_length=1)
    expected_revision: int | None = None


def _result(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("conflict"):
        raise HTTPException(status_code=409, detail=payload)
    if payload.get("ok") is False:
        raise HTTPException(status_code=400, detail=payload)
    return payload


@router.get("/tree", summary="Site → building → equipment → point tree")
def get_tree(state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    return {
        "ok": True,
        "revision": state.graph.revision,
        "allow_mutations": state.settings.allow_mutations,
        "tree": crud.build_tree(state.graph),
    }


@router.get("/meta-tags", summary="Predefined shipping-style meta tags for points")
def meta_tags() -> dict[str, str]:
    return crud.meta_tag_catalog()


@router.get("/dashboard", summary="Ops tag counts across points")
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


@router.post("/tags", summary="Batch point ops tags (Received / Not received / meta)")
def apply_tags(body: TagsBody, state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    try:
        return _result(
            crud.apply_point_tags(
                state.graph,
                updates=[u.model_dump(exclude_none=True) for u in body.updates],
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
