"""In-memory expiring store for SPARQL agent plans (A19)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from bldgts.graph.service import ConflictError, GraphService
from bldgts.sparql.update_plan import (
    AgentUpdateRejected,
    apply_compiled_changes,
    build_plan,
)
from rdflib import Graph, URIRef


@dataclass
class StoredPlan:
    plan_id: str
    plan_hash: str
    base_revision: int
    scope_iris: list[str]
    affected_iris: list[str]
    added: list[dict[str, str]]
    deleted: list[dict[str, str]]
    entity_changes: dict[str, Any]
    before: dict[str, Any]
    after: dict[str, Any]
    compiled: dict[URIRef, dict[str, Any]]
    created_at: float
    expires_at: float
    applied: bool = False


class AgentPlanStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plans: dict[str, StoredPlan] = {}

    def _purge(self) -> None:
        now = time.time()
        dead = [pid for pid, plan in self._plans.items() if plan.expires_at <= now]
        for pid in dead:
            del self._plans[pid]

    def put(self, plan: StoredPlan) -> None:
        with self._lock:
            self._purge()
            self._plans[plan.plan_id] = plan

    def get(self, plan_id: str) -> StoredPlan | None:
        with self._lock:
            self._purge()
            return self._plans.get(plan_id)


_STORE = AgentPlanStore()


def plan_store() -> AgentPlanStore:
    return _STORE


def create_plan(
    graph: GraphService,
    *,
    update_text: str,
    scope_iris: list[str],
    expected_revision: int | None,
    ttl_s: int,
    max_triples: int,
) -> dict[str, Any]:
    if expected_revision is not None and expected_revision != graph.revision:
        raise ConflictError(current=graph.revision, expected=expected_revision)
    built = build_plan(
        graph.state.model,
        update_text=update_text,
        scope_iris=scope_iris,
        base_revision=graph.revision,
        max_triples=max_triples,
    )
    compiled = built.pop("_compiled")
    now = time.time()
    stored = StoredPlan(
        plan_id=built["plan_id"],
        plan_hash=built["plan_hash"],
        base_revision=built["base_revision"],
        scope_iris=built["scope_iris"],
        affected_iris=built["affected_iris"],
        added=built["added"],
        deleted=built["deleted"],
        entity_changes=built["entity_changes"],
        before=built["before"],
        after=built["after"],
        compiled=compiled,
        created_at=now,
        expires_at=now + max(ttl_s, 1),
    )
    plan_store().put(stored)
    return {
        "ok": True,
        "plan_id": stored.plan_id,
        "plan_hash": stored.plan_hash,
        "base_revision": stored.base_revision,
        "expires_at": stored.expires_at,
        "scope_iris": stored.scope_iris,
        "affected_iris": stored.affected_iris,
        "added": stored.added,
        "deleted": stored.deleted,
        "entity_changes": stored.entity_changes,
        "before": stored.before,
        "after": stored.after,
        "revision": graph.revision,
    }


def apply_plan(
    graph: GraphService,
    *,
    plan_id: str,
    plan_hash: str,
    expected_revision: int | None,
    allow_mutations: bool,
) -> dict[str, Any]:
    if not allow_mutations:
        raise PermissionError("mutations disabled (set BLDGTS_ALLOW_MUTATIONS=true)")
    stored = plan_store().get(plan_id)
    if stored is None:
        raise AgentUpdateRejected("plan not found or expired")
    if stored.applied:
        raise AgentUpdateRejected("plan already applied")
    if stored.plan_hash != plan_hash:
        raise AgentUpdateRejected("plan hash mismatch")
    if time.time() > stored.expires_at:
        raise AgentUpdateRejected("plan expired")
    if expected_revision is not None and expected_revision != graph.revision:
        raise ConflictError(current=graph.revision, expected=expected_revision)
    if stored.base_revision != graph.revision:
        raise ConflictError(current=graph.revision, expected=stored.base_revision)

    compiled = stored.compiled

    def mutator(g: Graph) -> None:
        apply_compiled_changes(g, compiled)

    rev = graph.apply_mutation(
        mutator,
        note=f"agent_plan:{stored.plan_id}",
        expected_revision=graph.revision,
    )
    stored.applied = True
    graph.schedule_serialize()
    return {
        "ok": True,
        "revision": rev,
        "plan_id": stored.plan_id,
        "affected_iris": stored.affected_iris,
        "after": stored.after,
    }
