from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from brickts.api.deps import AppState
from brickts.api.routers import equipment, faults, health, model, points, sparql, timeseries
from brickts.graph.service import GraphService
from brickts.ingest import bootstrap_all_async
from brickts.logging import configure_logging
from brickts.settings import Settings
from brickts.store.registry import build_store_registry

log = logging.getLogger(__name__)

APP_DESCRIPTION = """
## Brick timeseries SPARQL API

Read-only SPARQL against a Brick RDF model, plus point lookup and timeseries JSON.
The model is the only path from a logical point to historian samples
([Brick timeseries storage](https://docs.brickschema.org/metadata/timeseries-storage.html)).

### Try it here (Swagger)

1. **GET** `/api/sparql/examples` — inventory / equipment / points query presets  
2. **POST** `/api/sparql` — paste any example `query` and Execute  
3. **GET** `/api/model/ttl` — download the site Turtle  
4. **GET** `/api/model/validate` — SPARQL invariant checks  
5. **GET** `/api/points/{point_id}/timeseries` — samples for a point id  

### Local Python tutorial (no HTML UI)

Fault math and progressive lessons live on your laptop:

```bash
uv run python scripts/lesson_01_mech_summary.py
uv run python scripts/lesson_02_fc1_points.py
uv run python scripts/lesson_03_fc1_dataframe.py
uv run python scripts/lesson_04_run_fc1.py
```

Edit `BASE_URL` in `scripts/lesson_config.py` (Render or `http://127.0.0.1:8000`).
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
        title="brickts",
        description=APP_DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
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
    app.include_router(equipment.router)
    app.include_router(points.router)
    app.include_router(timeseries.router)
    app.include_router(model.router)
    app.include_router(faults.router)
    return app
