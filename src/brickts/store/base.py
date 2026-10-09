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
    def read(
        self,
        timeseries_id: str,
        *,
        start: int | None = None,
        end: int | None = None,
        limit: int | None = None,
    ) -> list[Sample]: ...

    def write(self, timeseries_id: str, samples: list[Sample]) -> int: ...

    def exists(self, timeseries_id: str) -> bool: ...

    def series_ids(self) -> set[str]: ...

    def stats(self, timeseries_id: str) -> SeriesStats | None: ...

    def close(self) -> None: ...
