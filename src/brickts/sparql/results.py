from __future__ import annotations

import time
from typing import Any


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
    vars_ = [str(v) for v in results.vars]
    bindings: list[dict] = []
    for i, row in enumerate(results):
        if i >= max_rows:
            truncated = True
            break
        bnd: dict[str, dict] = {}
        for v in vars_:
            term = row[v]
            if term is None:
                continue
            bnd[v] = {
                "type": "uri"
                if getattr(term, "datatype", None) is None and str(term).startswith("http")
                else "literal",
                "value": str(term),
            }
            if hasattr(term, "language") and term.language:
                bnd[v]["xml:lang"] = term.language
            if hasattr(term, "datatype") and term.datatype:
                bnd[v]["datatype"] = str(term.datatype)
        bindings.append(bnd)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    head = {"vars": vars_}
    return {"head": head, "results": {"bindings": bindings}}, {
        "row_count": len(bindings),
        "truncated": truncated,
        "elapsed_ms": elapsed_ms,
    }
