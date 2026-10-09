from fastapi import APIRouter, Depends

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import TimeseriesBatchRequest
from brickts.services import timeseries as ts_svc

router = APIRouter(prefix="/api/timeseries", tags=["timeseries"])


@router.post("/query")
async def batch_timeseries(body: TimeseriesBatchRequest, state: AppState = Depends(get_app_state)):
    out = []
    for q in body.queries:
        try:
            payload = await ts_svc.read_point_timeseries(
                state.graph.state.union,
                state.stores,
                q.point_id,
                start=q.start,
                end=q.end,
                limit=q.limit,
                max_rows=state.settings.timeseries_max_rows,
            )
            out.append({"ok": True, **payload.__dict__})
        except Exception as exc:
            out.append({"ok": False, "point_id": q.point_id, "error": str(exc)})
    return {"results": out}
