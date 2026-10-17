from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from bldgts.api.deps import AppState
from bldgts.api.routers import agent, health, model, model_crud, points, sparql
from bldgts.graph.service import GraphService
from bldgts.ingest import bootstrap_all_async
from bldgts.logging import configure_logging
from bldgts.settings import Settings
from bldgts.store.registry import build_store_registry
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

log = logging.getLogger(__name__)

APP_DESCRIPTION = """
Building metadata tutorial API — SPARQL + timeseries + Haystack authoring UI.

**Wake (Render free tier)** — `GET /health` until `"ready": true`

**SPARQL** — `POST /api/sparql` or `/api/sparql/upload` with a `.rq` from `scripts/sparql/`

**Timeseries** — `GET /api/points/{id}/timeseries` (ids come from the Brick model only)

**Turtle** — `GET /api/model/ttl` downloads the graph and also writes repo-root **`building.ttl`**
on a background thread (easy to open, commit, push for tutorials)

**Model tree CRUD** (set `BLDGTS_ALLOW_MUTATIONS=true`) — `/api/model/tree`,
`/api/model/equip`, `/api/model/point`, `/api/model/hide`, `/api/model/tags`,
`/api/model/metadata`, `/api/model/rename`

**SPARQL agent plan/apply** (A19; keeps `/api/sparql` read-only) —
`POST /api/agent/plan`, `POST /api/agent/apply` for scoped `INSERT DATA`/`DELETE DATA`

**React UI** — Part 2 `checkpoint/web/` (Vite): model tree, typed metadata, saved checks,
SPARQL, agent plan review. Existing timeseries refs are never rewritten.
""".strip()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings().resolve(Path.cwd())
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        graph = GraphService(settings)
        stores = build_store_registry(graph.state.union, settings)
        sem = asyncio.Semaphore(settings.sparql_max_concurrency)
        ctx = AppState(
            settings=settings,
            graph=graph,
            stores=stores,
            ready=not settings.bootstrap_on_startup,
        )
        app.state.ctx = ctx
        app.state.sparql_sem = sem

        async def bootstrap_bg() -> None:
            try:
                await bootstrap_all_async(settings)
                ctx.stores = build_store_registry(graph.state.union, settings)
                ctx.ready = True
                log.info("bootstrap complete")
            except Exception as exc:  # noqa: BLE001 - surface in /health
                ctx.bootstrap_error = str(exc)
                log.exception("bootstrap failed")

        boot_task = None
        if settings.bootstrap_on_startup:
            boot_task = asyncio.create_task(bootstrap_bg())
            ctx.bootstrap_task = boot_task

        async def flusher():
            while True:
                await asyncio.sleep(max(settings.serialize_interval_s, 1))
                if settings.serialize_interval_s <= 0:
                    continue
                if graph.dirty:
                    await asyncio.to_thread(graph.serialize_atomic)

        task = None
        if settings.serialize_interval_s > 0:
            task = asyncio.create_task(flusher())
        try:
            yield
        finally:
            if boot_task:
                boot_task.cancel()
            if task:
                task.cancel()
            if graph.dirty:
                graph.serialize_atomic()
            for store in ctx.stores.values():
                await store.close()

    app = FastAPI(
        title="bldgts",
        description=APP_DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = int((time.perf_counter() - start) * 1000)
        log.info(
            "request",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "ms": ms,
            },
        )
        return response

    app.include_router(health.router)
    app.include_router(sparql.router)
    app.include_router(points.router)
    app.include_router(model.router)
    app.include_router(model_crud.router)
    app.include_router(agent.router)
    return app
