# App-base tests (no web UI)

Validate RDF CRUD with **in-process** FastAPI `TestClient` — no `npm`, no browser, no `bldgts serve`.

| Module | Role |
|--------|------|
| [`rdf_crud.py`](rdf_crud.py) | Helpers: `api_client`, `post_markers`, `guess_markers`, `assert_markers`, timeseries integrity |
| [`test_rdf_crud_markers.py`](test_rdf_crud_markers.py) | Template: guess → POST `/api/model/tags` → assert triples on the graph |
| [`test_model_crud.py`](test_model_crud.py) | Broader CRUD / TTL / gate coverage |
| [`test_haystack_suggest.py`](test_haystack_suggest.py) | Pure unit tests for defs + fuzzy guess (no HTTP) |

```bash
uv run pytest -q tests/test_rdf_crud_markers.py tests/test_haystack_suggest.py
```

For a future Part 3+ checkpoint: keep the same helper shapes (or copy `rdf_crud.py` next to that checkpoint’s tests) and point imports at that part’s package once `module-root` switches.
