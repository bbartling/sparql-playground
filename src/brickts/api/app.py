from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from brickts.api.deps import AppState
from brickts.api.routers import equipment, faults, health, model, points, sparql, timeseries
from brickts.graph.service import GraphService
from brickts.ingest import bootstrap_all_async
from brickts.logging import configure_logging
from brickts.settings import Settings
from brickts.store.registry import build_store_registry

log = logging.getLogger(__name__)


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

    app = FastAPI(title="brickts", lifespan=lifespan)
    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def root():
        return RedirectResponse(url="/ui")

    @app.get("/ui", response_class=HTMLResponse)
    def ui_page():
        return (static_dir / "index.html").read_text()

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
