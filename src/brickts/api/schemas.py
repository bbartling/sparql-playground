from __future__ import annotations

from pydantic import BaseModel, Field


class SparqlRequest(BaseModel):
    query: str = Field(min_length=1)


class HealthResponse(BaseModel):
    status: str = "ok"


class PointOut(BaseModel):
    point_id: str
    label: str
    brick_class: str
    owner_id: str
    timeseries_id: str | None = None
    unit: str | None = None


class TimeseriesOut(BaseModel):
    point_id: str
    timeseries_id: str
    samples: list[dict]
    truncated: bool


class FaultOut(BaseModel):
    rule_id: str
    title: str
    applicable: bool
    generic: bool
    reason: str


class TimeseriesQueryItem(BaseModel):
    point_id: str
    start: int | None = None
    end: int | None = None
    limit: int | None = None


class TimeseriesBatchRequest(BaseModel):
    queries: list[TimeseriesQueryItem]
