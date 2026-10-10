from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from brickts.api.deps import AppState, get_app_state
from brickts.api.schemas import (
    FC1_POINTS_QUERY,
    LIST_AHUS_QUERY,
    MECH_SUMMARY_QUERY,
    SparqlRequest,
)
from brickts.graph.sparql_guard import (
    SparqlRejected,
    SparqlSyntaxError,
    prepare_sparql,
    run_prepared,
)
from brickts.sparql.results import sparql_results_to_json

router = APIRouter(prefix="/api/sparql", tags=["sparql"])

_RQ_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,127}\.rq$")


def _lesson_sparql_dir() -> Path | None:
    """Tutorial .rq files shipped next to the app (see Dockerfile COPY)."""
    candidates = [
        Path.cwd() / "scripts" / "sparql",
        Path(__file__).resolve().parents[4] / "scripts" / "sparql",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return None

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
    "fc1_points": {
        "summary": "FC1 points on AHU_1 (lesson 2)",
        "description": "Same SPARQL as scripts/lesson_02 / scripts/sparql/02_fc1_points.rq.",
        "value": {"query": FC1_POINTS_QUERY},
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
        "or write your own SELECT/ASK. Prefer POST /api/sparql/upload to avoid "
        "JSON newline issues — upload a .rq file from scripts/sparql/."
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


@router.get(
    "/files",
    summary="List lesson SPARQL .rq files",
    description="Plain-text queries mirroring scripts/lesson_0*.py (also under scripts/sparql/).",
)
def list_lesson_files():
    root = _lesson_sparql_dir()
    if root is None:
        return {"files": [], "hint": "scripts/sparql not present on this host"}
    files = sorted(p.name for p in root.glob("*.rq"))
    return {
        "files": files,
        "upload": "POST /api/sparql/upload with one of these files (or your own .rq)",
        "download": "GET /api/sparql/files/{name}",
    }


@router.get(
    "/files/{name}",
    summary="Download one lesson .rq file",
    response_class=PlainTextResponse,
)
def get_lesson_file(name: str):
    if not _RQ_NAME.match(name):
        raise HTTPException(status_code=400, detail="invalid file name")
    root = _lesson_sparql_dir()
    if root is None:
        raise HTTPException(status_code=404, detail="scripts/sparql not available")
    path = root / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return PlainTextResponse(
        path.read_text(encoding="utf-8"),
        media_type="application/sparql-query",
    )


@router.post(
    "/upload",
    summary="Run SPARQL from an uploaded .rq file",
    description=(
        "Easiest Try-it-out path: Choose File → pick scripts/sparql/02_fc1_points.rq "
        "(or any .rq / .txt with a SELECT/ASK) → Execute. No JSON body needed."
    ),
)
async def sparql_upload(
    request: Request,
    state: AppState = Depends(get_app_state),
    file: UploadFile = File(..., description="SPARQL query file (.rq or .txt)"),
):
    raw = await file.read()
    if len(raw) > 200_000:
        raise HTTPException(status_code=400, detail="file too large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="file must be UTF-8 text") from exc
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty file")
    return await _run_query(request, state, text)
