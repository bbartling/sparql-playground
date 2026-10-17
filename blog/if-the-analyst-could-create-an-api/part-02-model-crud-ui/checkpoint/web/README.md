# Haystack model + SPARQL UI

Tutorial React UI for the bldgts API (smart-building IoT):

- **Model** — site → building → equipment → point tree; **Haystack markers**; hold-to-rename; right-click closest-match suggest
- **SPARQL** — browser editor with tutorial presets
- **Coverage** — marker counts across historized points

Turtle serializes to repo-root **`building.ttl`**.

## Run

Terminal 1 — API:

```bash
cd ..
BLDGTS_ALLOW_MUTATIONS=true uv run bldgts serve
```

Terminal 2 — UI:

```bash
npm install
npm run dev
```

Open http://127.0.0.1:5173 · Swagger http://127.0.0.1:8000/docs
