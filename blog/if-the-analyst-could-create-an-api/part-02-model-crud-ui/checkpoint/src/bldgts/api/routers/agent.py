"""SPARQL-only agent plan/apply endpoints (A19). Keeps /api/sparql read-only."""

from __future__ import annotations

from typing import Any

from bldgts.api.deps import AppState, get_app_state
from bldgts.graph.service import ConflictError
from bldgts.services import agent_plan as plans
from bldgts.sparql.update_plan import AgentUpdateRejected
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/agent", tags=["agent"])


class PlanBody(BaseModel):
    update: str = Field(min_length=1, max_length=50000)
    scope_iris: list[str] = Field(min_length=1, max_length=64)
    expected_revision: int | None = None


class ApplyBody(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)
    plan_hash: str = Field(min_length=64, max_length=64)
    expected_revision: int | None = None


def _conflict(exc: ConflictError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "ok": False,
            "conflict": True,
            "revision": exc.current,
            "expected_revision": exc.expected,
        },
    )


@router.post("/plan", summary="Build a reviewable SPARQL INSERT/DELETE DATA plan")
def create_plan(body: PlanBody, state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    try:
        return plans.create_plan(
            state.graph,
            update_text=body.update,
            scope_iris=body.scope_iris,
            expected_revision=body.expected_revision,
            ttl_s=state.settings.agent_plan_ttl_s,
            max_triples=state.settings.agent_plan_max_triples,
        )
    except ConflictError as exc:
        raise _conflict(exc) from exc
    except AgentUpdateRejected as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "error": str(exc)}) from exc


@router.post("/apply", summary="Apply an exact stored SPARQL agent plan")
def apply_plan(body: ApplyBody, state: AppState = Depends(get_app_state)) -> dict[str, Any]:
    try:
        return plans.apply_plan(
            state.graph,
            plan_id=body.plan_id,
            plan_hash=body.plan_hash,
            expected_revision=body.expected_revision,
            allow_mutations=state.settings.allow_mutations,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"ok": False, "error": str(exc)}) from exc
    except ConflictError as exc:
        raise _conflict(exc) from exc
    except AgentUpdateRejected as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "error": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "error": str(exc)}) from exc
