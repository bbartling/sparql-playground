from __future__ import annotations

from dataclasses import dataclass

from rdflib import Graph

from brickts.graph.namespaces import BLDG, REF
from brickts.store.base import TimeseriesStore


class TimeseriesConflict(Exception):
    pass


class TimeseriesNotFound(Exception):
    pass


@dataclass
class TimeseriesPayload:
    point_id: str
    timeseries_id: str
    samples: list[dict]
    truncated: bool


def resolve_timeseries_id(union: Graph, point_id: str) -> str:
    p = BLDG[point_id]
    refs = list(union.objects(p, REF.hasExternalReference))
    if len(refs) != 1:
        raise TimeseriesConflict("point must have exactly one external reference")
    ref = refs[0]
    ids = [str(x) for x in union.objects(ref, REF.hasTimeseriesId)]
    if len(ids) != 1:
        raise TimeseriesConflict("reference must have exactly one timeseries id")
    db_nodes = list(union.objects(ref, REF.storedAt))
    if len(db_nodes) != 1:
        raise TimeseriesConflict("reference must have storedAt database")
    return ids[0]


async def read_point_timeseries(
    union: Graph,
    stores: dict[str, TimeseriesStore],
    point_id: str,
    *,
    start: int | None = None,
    end: int | None = None,
    limit: int | None = None,
    max_rows: int,
) -> TimeseriesPayload:
    ts_id = resolve_timeseries_id(union, point_id)
    store = _pick_store(union, stores, point_id)
    if not await store.exists(ts_id):
        raise TimeseriesNotFound(ts_id)
    eff_limit = limit
    truncated = False
    if eff_limit is None or eff_limit > max_rows:
        eff_limit = max_rows + 1
        truncated = True
    samples = await store.read(ts_id, start=start, end=end, limit=eff_limit)
    if len(samples) > max_rows:
        samples = samples[:max_rows]
        truncated = True
    else:
        truncated = False
    return TimeseriesPayload(
        point_id=point_id,
        timeseries_id=ts_id,
        samples=[{"ts": s.ts, "value": s.value} for s in samples],
        truncated=truncated,
    )


def _pick_store(union: Graph, stores: dict[str, TimeseriesStore], point_id: str) -> TimeseriesStore:
    p = BLDG[point_id]
    ref = next(union.objects(p, REF.hasExternalReference))
    db = next(union.objects(ref, REF.storedAt))
    key = str(db)
    if key in stores:
        return stores[key]
    return next(iter(stores.values()))
