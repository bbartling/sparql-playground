from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import FC1_POINTS_QUERY, SparqlRequest
from brickts.graph.sparql_guard import (
    SparqlRejected,
    SparqlSyntaxError,
    prepare_sparql,
    run_prepared,
)
from brickts.sparql.results import sparql_results_to_json

router = APIRouter(prefix="/api/sparql", tags=["sparql"])


async def _run_query(request: Request, state: AppState, text: str):
    settings = state.settings
    try:
        prepared = prepare_sparql(text, settings)
    except SparqlSyntaxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparqlRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sem = request.app.state.sparql_sem
    async with sem:
        try:
            results = await asyncio.wait_for(
                run_in_threadpool(run_prepared, state.graph.state.union, prepared),
                timeout=settings.sparql_timeout_s,
            )
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail="query timeout") from exc
    body, meta = sparql_results_to_json(results, max_rows=settings.sparql_max_rows)
    return {"results": body, "meta": meta}


@router.post(
    "",
    summary="Run SPARQL (JSON)",
    description="Used by lesson scripts, or paste SPARQL from scripts/sparql/*.rq.",
)
async def sparql_post(
    payload: Annotated[
        SparqlRequest,
        Body(
            openapi_examples={
                "fc1_points": {
                    "summary": "FC1 points (copy of scripts/sparql/02_fc1_points.rq)",
                    "value": {"query": FC1_POINTS_QUERY},
                }
            }
        ),
    ],
    request: Request,
    state: AppState = Depends(get_app_state),
):
    return await _run_query(request, state, payload.query)


@router.post(
    "/upload",
    summary="Run SPARQL from a local .rq file",
    description=(
        "Copy queries from the tutorial repo (scripts/sparql/*.rq), "
        "then Choose File → Execute. Nothing is downloaded from the API."
    ),
)
async def sparql_upload(
    request: Request,
    state: AppState = Depends(get_app_state),
    file: UploadFile = File(..., description="UTF-8 .rq or .txt from your clone"),
):
    raw = await file.read()
    if len(raw) > 200_000:
        raise HTTPException(status_code=400, detail="file too large")
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="file must be UTF-8 text") from exc
    if not text:
        raise HTTPException(status_code=400, detail="empty file")
    return await _run_query(request, state, text)
