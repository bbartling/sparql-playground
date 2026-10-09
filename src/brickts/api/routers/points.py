from fastapi import APIRouter, Depends, HTTPException

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import PointOut, TimeseriesOut
from brickts.services import points as point_svc
from brickts.services import timeseries as ts_svc

router = APIRouter(prefix="/api/points", tags=["points"])


@router.get("/{point_id}", response_model=PointOut)
def get_point(point_id: str, state: AppState = Depends(get_app_state)):
    pt = point_svc.get_point(state.graph.state.union, point_id)
    if pt is None:
        raise HTTPException(status_code=404, detail="unknown point")
    return PointOut(**pt.__dict__)


@router.get("/{point_id}/timeseries", response_model=TimeseriesOut)
async def point_timeseries(
    point_id: str,
    start: int | None = None,
    end: int | None = None,
    limit: int | None = None,
    state: AppState = Depends(get_app_state),
):
    if point_svc.get_point(state.graph.state.union, point_id) is None:
        raise HTTPException(status_code=404, detail="unknown point")
    try:
        payload = await ts_svc.read_point_timeseries(
            state.graph.state.union,
            state.stores,
            point_id,
            start=start,
            end=end,
            limit=limit,
            max_rows=state.settings.timeseries_max_rows,
        )
    except ts_svc.TimeseriesConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ts_svc.TimeseriesNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TimeseriesOut(**payload.__dict__)
