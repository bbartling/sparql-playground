from fastapi import APIRouter, Depends, HTTPException, Query

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import FaultOut, PointOut, RoleBindingOut, RuleRunOut
from brickts.services import faults as fault_svc
from brickts.services import points as point_svc
from brickts.services import rules as rule_svc

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


@router.get("/{equipment_id}/faults/{rule_id}/lesson")
def fault_lesson(
    equipment_id: str,
    rule_id: str,
    state: AppState = Depends(get_app_state),
):
    from open_fdd.rules import RULES

    rule = next((r for r in RULES if r.id == rule_id), None)
    if rule is None:
        raise HTTPException(status_code=404, detail="unknown rule")
    try:
        point_svc.validate_equipment_id(equipment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="unknown equipment") from exc
    roles = list(getattr(rule, "required_roles", ()) or ())
    lessons = []
    for role in roles:
        try:
            q = rule_svc.role_lesson_query(equipment_id, role)
            bindings = rule_svc.resolve_role_bindings(state.graph.state.union, equipment_id, [role])
            lessons.append(
                {
                    "role": role,
                    "query": q,
                    "binding": RoleBindingOut(**bindings[0].__dict__).model_dump(),
                }
            )
        except ValueError as exc:
            lessons.append({"role": role, "query": None, "error": str(exc)})
    return {
        "rule_id": rule_id,
        "title": getattr(rule, "title", rule_id),
        "equation": getattr(rule, "equation", ""),
        "summary": getattr(rule, "summary", ""),
        "required_roles": roles,
        "lessons": lessons,
    }


@router.post("/{equipment_id}/faults/{rule_id}/run", response_model=RuleRunOut)
async def run_fault_rule(
    equipment_id: str,
    rule_id: str,
    limit: int | None = Query(default=None, ge=1, le=500000),
    state: AppState = Depends(get_app_state),
):
    if not state.ready:
        raise HTTPException(status_code=503, detail="timeseries bootstrap still running")
    try:
        result = await rule_svc.run_equipment_rule(
            state.graph.state.union,
            state.stores,
            equipment_id=equipment_id,
            rule_id=rule_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RuleRunOut(
        rule_id=result.rule_id,
        equipment_id=result.equipment_id,
        status=result.status,
        fault_hours=result.fault_hours,
        fault_pct=result.fault_pct,
        sample_count=result.sample_count,
        fault_sample_count=result.fault_sample_count,
        bindings=[RoleBindingOut(**b.__dict__) for b in result.bindings],
        evidence=result.evidence,
    )
