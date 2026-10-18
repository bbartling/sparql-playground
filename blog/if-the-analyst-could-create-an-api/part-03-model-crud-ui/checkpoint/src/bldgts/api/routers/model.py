from __future__ import annotations

from typing import Literal

from bldgts.api.deps import AppState, get_app_state
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get(
    "/ttl",
    summary="Download RDF as Turtle",
    description=(
        "`scope=model` (default): in-memory site graph with points + timeseries refs. "
        "Also kicks a background write to repo-root `building.ttl`. "
        "`scope=site`: hand-authored model/site.ttl only (equipment/zones/parts, no points)."
    ),
)
def download_ttl(
    scope: Literal["model", "site"] = Query(
        default="model",
        description="model = full building graph; site = site.ttl skeleton only",
    ),
    state: AppState = Depends(get_app_state),
):
    if scope == "site":
        path = state.settings.site_model_path
        if not path.exists():
            raise HTTPException(status_code=404, detail="site.ttl not found")
        text = path.read_text(encoding="utf-8")
        filename = "site.ttl"
    else:
        text = state.graph.state.model.serialize(format="turtle")
        filename = "building.ttl"
        # Tutorial-friendly: persist root-level building.ttl on a side thread.
        state.graph.schedule_serialize()

    return Response(
        content=text,
        media_type="text/turtle; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
