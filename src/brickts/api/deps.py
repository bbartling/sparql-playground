from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from brickts.graph.service import GraphService
from brickts.settings import Settings
from brickts.store.base import TimeseriesStore


@dataclass
class AppState:
    settings: Settings
    graph: GraphService
    stores: dict[str, TimeseriesStore]


def get_app_state(request: Request) -> AppState:
    return request.app.state.ctx
