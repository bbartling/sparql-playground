# Part 4 — Data viz + Timescale cutover *(placeholder)*

**Series:** [If the analyst could create an API](../README.md)  
**Builds on:** [Part 3](../part-03-model-crud-ui/) (Haystack-native UI / CRUD)

## Intent (future freeze)

- Cut the live timeseries path from **SQLite → PostgreSQL / Timescale**
- Add a **data visualization** surface over opaque timeseries ids (charts driven by the model, not raw column names)
- Optional: ingest samples already proven from the edge in [Part 2](../part-02-nf-edge-sensors/) —
  see [`agent_spec/NORMAL_FRAMEWORK.md`](../../../agent_spec/NORMAL_FRAMEWORK.md)

## This folder now

Bare placeholder only:

- `GIT_SHA.txt` — fill when frozen
- `checkpoint/` — empty until this part ships an app base

Hands-on SQL learning remains the independent course at [`lessons/sql/`](../../../lessons/sql/) (not owned by this part).

## Next

[Part 5 — FDD with Open-FDD on Postgres](../part-05-fdd-openfdd-postgres/)
