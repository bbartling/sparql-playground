from __future__ import annotations

import time
from typing import Any

from rdflib import BNode, Literal, URIRef


def sparql_results_to_json(results, *, max_rows: int) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    truncated = False
    if isinstance(results, bool):
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {"head": {"vars": []}, "boolean": results}, {
            "row_count": 1,
            "truncated": False,
            "elapsed_ms": elapsed_ms,
        }
    if getattr(results, "askAnswer", None) is not None:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {"head": {"vars": []}, "boolean": bool(results.askAnswer)}, {
            "row_count": 1,
            "truncated": False,
            "elapsed_ms": elapsed_ms,
        }
    graph_result = getattr(results, "type", None) in {"CONSTRUCT", "DESCRIBE"}
    vars_ = ["subject", "predicate", "object"] if graph_result else [str(v) for v in results.vars]
    bindings: list[dict] = []
    for i, row in enumerate(results.graph if graph_result else results):
        if i >= max_rows:
            truncated = True
            break
        bnd: dict[str, dict] = {}
        for column, v in enumerate(vars_):
            term = row[column] if graph_result else row[v]
            if term is None:
                continue
            kind = (
                "uri"
                if isinstance(term, URIRef)
                else "bnode"
                if isinstance(term, BNode)
                else "literal"
            )
            bnd[v] = {"type": kind, "value": str(term)}
            if isinstance(term, Literal):
                if term.language:
                    bnd[v]["xml:lang"] = term.language
                if term.datatype:
                    bnd[v]["datatype"] = str(term.datatype)
        bindings.append(bnd)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    head = {"vars": vars_}
    return {"head": head, "results": {"bindings": bindings}}, {
        "row_count": len(bindings),
        "truncated": truncated,
        "elapsed_ms": elapsed_ms,
    }
