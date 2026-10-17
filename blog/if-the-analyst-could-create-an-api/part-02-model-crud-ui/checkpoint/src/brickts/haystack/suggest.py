from __future__ import annotations

import difflib
import re
from typing import Any

from brickts.haystack.defs import catalog_for_level, load_defs_index

_TOKEN = re.compile(r"[a-z0-9]+", re.I)


def _normalize(text: str) -> str:
    return " ".join(_TOKEN.findall(text.lower()))


def suggest_markers(
    query: str,
    level: str,
    *,
    n: int = 8,
    cutoff: float = 0.3,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Closest Haystack symbols for a node name / freeform query at a tree level."""
    q = _normalize(query)
    if not q:
        return []
    catalog = catalog_for_level(level, path=path)
    index = load_defs_index(path)
    tokens = set(q.split())

    scored: list[tuple[float, str]] = []
    for sym, doc in catalog.items():
        blob = _normalize(f"{sym} {doc.split(chr(10), 1)[0]}")
        seq = difflib.SequenceMatcher(None, q, blob).ratio()
        # Boost exact token overlap (e.g. "temp" in "discharge air temp").
        overlap = len(tokens & set(_normalize(sym).split())) / max(len(tokens), 1)
        # Prefer symbols that appear as substrings of the query.
        substr = 0.25 if sym in q.replace(" ", "") or sym in q else 0.0
        for tok in tokens:
            if tok == sym or (len(tok) > 2 and (tok in sym or sym in tok)):
                substr = max(substr, 0.35)
        score = max(seq, overlap + substr)
        if score >= cutoff or overlap > 0 or substr > 0:
            scored.append((score, sym))

    scored.sort(key=lambda item: (-item[0], item[1]))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for score, sym in scored:
        if sym in seen:
            continue
        seen.add(sym)
        out.append(
            {
                "symbol": sym,
                "doc": catalog.get(sym) or index.get(sym, {}).get("doc", ""),
                "score": round(score, 4),
            }
        )
        if len(out) >= n:
            break
    return out
