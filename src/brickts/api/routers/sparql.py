from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import LIST_AHUS_QUERY, MECH_SUMMARY_QUERY, SparqlRequest
from brickts.graph.sparql_guard import (
    SparqlRejected,
    SparqlSyntaxError,
    prepare_sparql,
    run_prepared,
)
from brickts.sparql.results import sparql_results_to_json

router = APIRouter(prefix="/api/sparql", tags=["sparql"])

_SPARQL_BODY_EXAMPLES = {
    "mech_summary": {
        "summary": "Mechanical system roll-up",
        "description": "Counts equipment by Brick kind (AHUs, zones, boilers, …).",
        "value": {"query": MECH_SUMMARY_QUERY},
    },
    "list_ahus": {
        "summary": "List AHUs",
        "description": "Every Air_Handler_Unit in the site graph.",
        "value": {"query": LIST_AHUS_QUERY},
    },
}


@router.get(
    "/examples",
    summary="List SPARQL tutorial presets",
    description=(
        "Returns inventory queries (mech summary, equipment lists, points). "
        "Or pick a prefilled example on POST /api/sparql in Swagger."
    ),
)
def list_examples(state: AppState = Depends(get_app_state)):
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


@router.post(
    "",
    summary="Run a read-only SPARQL query",
    description=(
        "Pick an example from the dropdown (pre-fills the body / curl), "
        "or write your own SELECT/ASK. More presets: GET /api/sparql/examples."
    ),
)
async def sparql_post(
    payload: Annotated[
        SparqlRequest,
        Body(openapi_examples=_SPARQL_BODY_EXAMPLES),
    ],
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
