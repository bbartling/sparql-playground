from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Sample:
    ts: int
    value: float


@dataclass(frozen=True, slots=True)
class SeriesStats:
    timeseries_id: str
    count: int
    min_ts: int | None
    max_ts: int | None


@runtime_checkable
class TimeseriesStore(Protocol):
    async def read(
        self,
        timeseries_id: str,
        *,
        start: int | None = None,
        end: int | None = None,
        limit: int | None = None,
    ) -> list[Sample]: ...

    async def write(self, timeseries_id: str, samples: list[Sample]) -> int: ...

    async def exists(self, timeseries_id: str) -> bool: ...

    async def series_ids(self) -> set[str]: ...

    async def stats(self, timeseries_id: str) -> SeriesStats | None: ...

    async def close(self) -> None: ...
