# Haystack model editor

Model tree → **Edit** → left-click any row → rename, markers, typed metadata → **Save**. Review suggestions explicitly. Saved model validation uses the supported Haystack profile; Edit suppresses repeated validation colors and details. SPARQL and RDF tabs inspect the same live graph.

Run the API from the **repository root**:

```bash
uv sync
BLDGTS_ALLOW_MUTATIONS=true uv run bldgts serve
```

Run the UI from this `checkpoint/web/` directory:

```bash
npm ci
npm run dev
```

Open http://127.0.0.1:5173. API docs: http://127.0.0.1:8000/docs. Vite proxies API requests to port 8000. `npm run build` checks TypeScript and produces the production bundle. Metadata edits persist to repo-root `building.ttl` and the crash-recovery snapshot.

See the Part 3 [modeling contract](../../HAYSTACK_MODELING.md). Backend regression tests run from the repository root with `uv run pytest -q`.
