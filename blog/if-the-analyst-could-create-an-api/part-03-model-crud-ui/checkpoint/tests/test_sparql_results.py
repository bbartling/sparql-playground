import asyncio
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from bldgts.api.routers.sparql import _run_query
from bldgts.settings import Settings
from bldgts.sparql.results import sparql_results_to_json
from fastapi import HTTPException
from rdflib import BNode, Graph, Literal, URIRef


def test_select_preserves_rdf_term_kinds():
    graph = Graph()
    graph.add((URIRef("urn:point"), URIRef("urn:name"), Literal("https://example.org/name")))
    graph.add((BNode("part"), URIRef("urn:name"), Literal("Part", lang="en")))
    result, _ = sparql_results_to_json(graph.query("SELECT ?s ?o WHERE {?s ?p ?o}"), max_rows=10)
    rows = result["results"]["bindings"]
    assert any(r["s"]["type"] == "uri" and r["s"]["value"] == "urn:point" for r in rows)
    assert any(r["s"]["type"] == "bnode" for r in rows)
    assert all(r["o"]["type"] == "literal" for r in rows)
    assert any(r["o"].get("xml:lang") == "en" for r in rows)


@pytest.mark.parametrize(
    "query",
    [
        "CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}",
        "DESCRIBE <urn:point>",
    ],
)
def test_graph_query_has_bounded_triple_projection(query):
    graph = Graph()
    for n in range(3):
        graph.add((URIRef("urn:point"), URIRef(f"urn:p{n}"), Literal(n)))
    result, meta = sparql_results_to_json(graph.query(query), max_rows=1)
    assert result["head"]["vars"] == ["subject", "predicate", "object"]
    assert len(result["results"]["bindings"]) == 1
    assert meta["truncated"]


def test_lazy_result_timeout_keeps_concurrency_slot_until_worker_finishes():
    async def check():
        started = asyncio.Event()
        loop = asyncio.get_running_loop()

        class LazyResult:
            vars = ["value"]

            def __iter__(self):
                loop.call_soon_threadsafe(started.set)
                time.sleep(0.1)
                yield {"value": Literal(1)}

        sem = asyncio.Semaphore(1)
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(sparql_sem=sem)))
        state = SimpleNamespace(
            settings=Settings(sparql_timeout_s=0.01),
            graph=SimpleNamespace(state=SimpleNamespace(union=Graph())),
        )
        with patch("bldgts.api.routers.sparql.run_prepared", return_value=LazyResult()):
            with pytest.raises(HTTPException) as failure:
                await _run_query(request, state, "SELECT ?value WHERE {?s ?p ?value}")
            assert failure.value.status_code == 504
            assert started.is_set()
            assert sem.locked()
            await asyncio.wait_for(sem.acquire(), timeout=1)
            sem.release()

    asyncio.run(check())
