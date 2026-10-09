from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import SparqlRequest
from brickts.graph.sparql_guard import (
    SparqlRejected,
    SparqlSyntaxError,
    prepare_sparql,
    run_prepared,
)
from brickts.sparql.results import sparql_results_to_json

router = APIRouter(prefix="/api/sparql", tags=["sparql"])


@router.get("/examples")
def list_examples(state: AppState = Depends(get_app_state)):
    root = state.settings.data_dir.parent / "src" / "brickts" / "sparql" / "examples"
    if not root.exists():
        root = state.settings.model_path.parent.parent / "src" / "brickts" / "sparql" / "examples"
    from pathlib import Path

    ex_dir = Path(__file__).resolve().parent.parent.parent / "sparql" / "examples"
    items = []
    for path in sorted(ex_dir.glob("*.rq")):
        items.append(
            {"id": path.stem, "title": path.stem.replace("_", " "), "query": path.read_text()}
        )
    return {"examples": items}


async def _run_query(request, state: AppState, text: str):
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


@router.post("")
async def sparql_post(
    payload: SparqlRequest,
    request: Request,
    state: AppState = Depends(get_app_state),
):
    return await _run_query(request, state, payload.query)


@router.get("")
async def sparql_get(
    request: Request,
    query: str = Query(..., min_length=1),
    state: AppState = Depends(get_app_state),
):
    return await _run_query(request, state, query)
