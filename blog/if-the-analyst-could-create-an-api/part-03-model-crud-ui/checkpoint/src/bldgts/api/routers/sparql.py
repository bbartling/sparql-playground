from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Annotated

from bldgts.api.deps import AppState, get_app_state
from bldgts.api.schemas import FC1_POINTS_QUERY, SparqlRequest
from bldgts.graph.sparql_guard import (
    SparqlRejected,
    SparqlSyntaxError,
    prepare_sparql,
    run_prepared,
)
from bldgts.sparql.results import sparql_results_to_json
from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile

router = APIRouter(prefix="/api/sparql", tags=["sparql"])

_SAFE_EXAMPLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.rq$")


def _examples_dir(state: AppState) -> Path:
    path = state.settings.sparql_examples_dir
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="SPARQL examples directory missing")
    return path.resolve()


def _resolve_example(state: AppState, name: str) -> Path:
    if not _SAFE_EXAMPLE.match(name):
        raise HTTPException(status_code=400, detail="invalid example name")
    root = _examples_dir(state)
    path = (root / name).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="example not found")
    return path


async def _run_query(request: Request, state: AppState, text: str):
    settings = state.settings
    try:
        prepared = prepare_sparql(text, settings)
    except SparqlSyntaxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparqlRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def evaluate():
        # rdflib SELECT results are lazy: consume them inside the timed worker too.
        results = run_prepared(state.graph.state.union, prepared)
        return sparql_results_to_json(results, max_rows=settings.sparql_max_rows)

    sem = request.app.state.sparql_sem
    await sem.acquire()
    worker = asyncio.create_task(asyncio.to_thread(evaluate))

    def completed(task):
        sem.release()
        # Observe late failures after an HTTP timeout, avoiding unhandled task errors.
        if not task.cancelled():
            task.exception()

    worker.add_done_callback(completed)
    try:
        # A timeout cannot kill a Python thread. Keep its semaphore slot occupied
        # until it really finishes, so repeated timeouts cannot spawn unlimited work.
        body, meta = await asyncio.wait_for(
            asyncio.shield(worker), timeout=settings.sparql_timeout_s
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="query timeout") from exc
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


@router.get(
    "/examples",
    summary="List bundled SPARQL tutorial .rq files",
    description="Names from scripts/sparql/ for the browser SPARQL editor.",
)
def list_examples(state: AppState = Depends(get_app_state)) -> dict[str, list[str]]:
    root = _examples_dir(state)
    names = sorted(p.name for p in root.glob("*.rq") if p.is_file())
    return {"examples": names}


@router.get(
    "/examples/{name}",
    summary="Load one bundled SPARQL .rq file",
)
def get_example(name: str, state: AppState = Depends(get_app_state)) -> dict[str, str]:
    path = _resolve_example(state, name)
    return {"name": name, "query": path.read_text(encoding="utf-8")}
