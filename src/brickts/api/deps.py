from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request

from brickts.graph.service import GraphService
from brickts.settings import Settings
from brickts.store.base import TimeseriesStore


@dataclass
class AppState:
    settings: Settings
    graph: GraphService
    stores: dict[str, TimeseriesStore]
    ready: bool = False
    bootstrap_error: str | None = None
    bootstrap_task: object | None = field(default=None, repr=False)


def get_app_state(request: Request) -> AppState:
    return request.app.state.ctx
