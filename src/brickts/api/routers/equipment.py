from fastapi import APIRouter, Depends, HTTPException, Query

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import FaultOut, PointOut
from brickts.services import faults as fault_svc
from brickts.services import points as point_svc

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


@router.get("")
def list_equipment(state: AppState = Depends(get_app_state)):
    return {"equipment": point_svc.list_equipment(state.graph.state.union)}


@router.get("/{equipment_id}/points")
def equipment_points(
    equipment_id: str,
    brick_class: str | None = None,
    tags: str | None = None,
    parent_class: str | None = None,
    include_subclasses: bool = True,
    include_fed_zones: bool = False,
    state: AppState = Depends(get_app_state),
):
    try:
        point_svc.validate_equipment_id(equipment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="unknown equipment") from exc
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    try:
        pts = point_svc.find_points(
            state.graph.state.union,
            equipment_id,
            brick_class=brick_class,
            tags=tag_list,
            parent_class=parent_class,
            include_subclasses=include_subclasses,
            include_fed_zones=include_fed_zones,
        )
    except ValueError as exc:
        msg = str(exc)
        if "class" in msg:
            raise HTTPException(status_code=422, detail=msg) from exc
        raise HTTPException(status_code=404, detail=msg) from exc
    if not pts and not point_svc.get_point(state.graph.state.union, equipment_id):
        # ensure equipment exists in model
        from brickts.graph.namespaces import BLDG

        if (BLDG[equipment_id], None, None) not in state.graph.state.model:
            q = f"ASK {{ bldg:{equipment_id} ?p ?o . }}"
            if not bool(state.graph.state.union.query(q, initNs={"bldg": BLDG})):
                raise HTTPException(status_code=404, detail="unknown equipment")
    return {
        "points": [PointOut(**p.__dict__) for p in pts],
    }


@router.get("/{equipment_id}/faults", response_model=list[FaultOut])
def equipment_faults(
    equipment_id: str,
    include_generic: bool = Query(default=True),
    state: AppState = Depends(get_app_state),
):
    try:
        rows = fault_svc.list_faults(
            state.graph.state.union, equipment_id, include_generic=include_generic
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [FaultOut(**r.__dict__) for r in rows]
