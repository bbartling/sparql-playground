from __future__ import annotations

from dataclasses import dataclass, field

from bldgts.graph.service import GraphService
from bldgts.settings import Settings
from bldgts.store.base import TimeseriesStore
from fastapi import Request


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
