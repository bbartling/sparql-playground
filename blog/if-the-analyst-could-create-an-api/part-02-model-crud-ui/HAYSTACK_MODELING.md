# Part 2 modeling contract

This checkpoint is a Haystack authoring UI over an RDF application model. The live seed is **Haystack-only** (markers + typed tags + `siteRef`/`equipRef`/`spaceRef`). Opaque timeseries references (`ref:TimeseriesReference`) remain the historian link. It does not implement the Haystack HTTP protocol, Zinc/Hayson export, or complete Haystack ontology conformance. The UI calls its checks the **supported Haystack profile** for that reason.

## Required, recommended, and conditional

| Entity | Required in this app profile | Recommended / conditional |
|---|---|---|
| Site / building | Explicit `site` marker; existing RDF identity and display name | Site `tz` recommended, required when referenced by a historized point; address and area are useful enrichment |
| Equipment / part | Explicit `equip`; valid `siteRef` to an explicitly tagged site | Equipment subtype such as `ahu`/`fan`; `equipRef` when nesting equipment; optional `spaceRef` |
| Floor / space | `space`; valid `siteRef` | Appropriate location marker such as `floor`; the legacy Brick hierarchy remains visible |
| Point | `point`; exactly one `sensor`, `cmd`, `sp`, `synthetic`; `kind` (`Number`, `Bool`, `Str`); valid `siteRef` and `equipRef` | Numeric `unit`; `enum` for a string enumeration; descriptive subject/quantity markers |
| Point with `his` | Point requirements plus valid `tz`, matching the referenced site's explicit timezone; `hisMode` | `hisMode` values come from vendored definitions: `sampled`, `cov`, `consumption`; only use `his` when history exists |

Haystack tags have values as well as markers. `kind: "Number"`, `unit: "°F"`, and `siteRef: @Building_50` are not markers. `hisTotalized` is a marker. A numeric kind alone cannot tell whether a fan command is a percentage, frequency, or Boolean enable; inspect the source.

The UI's severity policy is:

- **Red:** missing required metadata, invalid values, conflicting function markers, or invalid references.
- **Yellow:** no required errors, but recommended information remains missing.
- **Green:** no issues detected by the supported profile. This is not a certification of the full Haystack ontology, actual device capabilities, or physical unit dimensions.

Parent status includes the parent's own issues and descendant issues. A completed point cannot make an incomplete parent green. There is no Brick migration overlay in the live app.

## Authoring workflow

Use **Edit**, then left-click any tree row to edit its display name, markers, and typed metadata. A display-name change preserves the stable entity ID and timeseries ID. Keep Edit focused on authoring; inspect saved validation through the single validation surface when needed. Guesses are proposals to review and explicitly add. They cannot infer timezone, engineering units, or a point's actual capabilities from an ambiguous BAS name.

Use the building with its own street address as the site for a new Haystack-native model. The tree recursively includes sites, buildings, floors, spaces, equipment, parts, and every visible point. Unattached records remain visible as roots instead of disappearing. The current `Site → Building` structure is inherited from the Brick tutorial. Saving a valid point `equipRef` updates its Brick ownership and inverse relationship together, so the point moves in the tree and SPARQL consistently. Equipment `siteRef` describes Haystack membership; it does not relocate the legacy physical site/building hierarchy. Reworking that hierarchy requires an explicit topology decision for the next part. Avoid treating campus and building as two independent Haystack sites for the same physical facility; choose the correct site record and reference it consistently.

## Typed metadata API and RDF mapping

The UI uses the existing mutation gate (`BLDGTS_ALLOW_MUTATIONS=true`), copy-on-write graph validation, optimistic revisions, and Turtle persistence. A batch replaces the entity's complete explicit value-tag dictionary. Include existing tags that should remain. An omitted `markers` field preserves markers; a supplied marker array replaces them.

```json
{
  "expected_revision": 12,
  "updates": [{
    "entity_id": "AHU_1_DA_P",
    "markers": ["point", "sensor", "discharge", "air", "pressure"],
    "metadata": {
      "kind": {"kind": "Str", "value": "Number"},
      "siteRef": {"kind": "Ref", "value": "Building_50"},
      "equipRef": {"kind": "Ref", "value": "AHU_1"}
    }
  }]
}
```

Send to `POST /api/model/metadata`. These are illustrative identifiers: choose the appropriate site/equipment and verify units against source data. Malformed typed input fails the batch; semantically incomplete drafts can be saved and reported red. A stale revision returns 409. Incomplete drafting is necessary for gradually tagging a tree; saving does not mean the model is valid.

Markers remain `bts:hasHaystackMarker` string values. Each value tag is a `bts:hasHaystackTag` node with `bts:tagName`, `bts:tagKind`, and `bts:tagValue`. A Ref stores an RDF IRI, Number/Bool store RDF typed literals, and Str stores a literal. This is a documented application mapping, not a standard Haystack RDF serialization.

Discover metadata using the existing SPARQL API:

```sparql
PREFIX bts: <https://example.org/openfdd/bldgts#>
SELECT ?entity ?name ?kind ?value WHERE {
  ?entity bts:hasHaystackTag ?tag .
  ?tag bts:tagName ?name ; bts:tagKind ?kind ; bts:tagValue ?value .
}
ORDER BY ?entity ?name
```

## AI agent boundary

`POST /api/sparql` remains read-only. Agents discover markers, typed metadata, relationships, revision, and opaque timeseries references with SELECT/ASK/CONSTRUCT/DESCRIBE against the parsed graph. There is no filesystem/shell tool for agents, no Turtle text-search endpoint, and no raw-RDF grep. The fuzzy marker catalog matches BAS display labels only; it is not a graph query. Portable Turtle is an export/recovery artifact parsed and serialized with rdflib — never treated as a searchable string database.

### Scoped SPARQL plan / apply (A19)

Agents persist changes through:

1. `POST /api/agent/plan` — body: `{ "update": "<SPARQL UPDATE>", "scope_iris": ["…"], "expected_revision": N }`
2. Human (or tool) reviews the server-built plan (added/deleted triples, affected entities, before/after profile issues, `plan_id`, `plan_hash`)
3. `POST /api/agent/apply` — body: `{ "plan_id": "…", "plan_hash": "…", "expected_revision": N }` with `BLDGTS_ALLOW_MUTATIONS=true`

Supported update subset: ground `DELETE DATA` / `INSERT DATA` only (use `;` between operations). Allowed predicates: `rdfs:label`, `bts:hasHaystackMarker`, `bts:hasHaystackTag`, `bts:tagName`, `bts:tagKind`, `bts:tagValue`. Linked tag nodes are matched by **tag name**: inserting a new `kind` tag replaces the previous `kind` value node; other metadata names stay put. Rejected: any other SPARQL algebra, named graphs, `SERVICE`/`LOAD`/`CLEAR`/`DROP`/`CREATE`/`MOVE`/`COPY`/`ADD`/`FROM`/`USING`, ontology edits, `rdf:type` / identity changes, Database nodes, and timeseries reference / id / storedAt triples.

Plans expire (`BLDGTS_AGENT_PLAN_TTL_S`, default 600s), cannot expand scope at apply time, and fail on hash mismatch, replay, stale revision, or mutations disabled. Apply uses the same copy-on-write + profile validation path as the UI (including equipRef ownership bridge). Incomplete semantic drafts may save and show red/yellow; malformed typed input fails the whole batch.

UI mutation routes (`/api/model/metadata`, rename, tags) remain for the human editor. The Agent tab is the SPARQL-only review surface; the Model tree continues to show applied agent edits after refresh.

The SPARQL endpoint consumes lazy results in its timed worker, preserves RDF term types, and projects CONSTRUCT/DESCRIBE graphs as bounded subject/predicate/object JSON bindings. A timeout releases the HTTP request; Python threads cannot be killed, so their concurrency slots remain occupied until they finish. Process isolation is a later hard timeout requirement for untrusted workloads.

## Export, reboot, transfer, and crash recovery

- `GET /api/model/ttl?scope=model` downloads the entire live application model as Turtle. `POST /api/model/flush` synchronously completes an on-disk snapshot. Export only the model, not the ontology union.
- The application atomically writes `building.ttl` and `BLDGTS_SNAPSHOT_PATH` (default `var/graph.snapshot.ttl`). A SHA-256 journal binds the recoverable revision to the actual completed snapshot bytes. Edits made while a write is in progress remain dirty for the next write.
- On reboot, a snapshot at least as new as the configured seed is loaded. Otherwise the seed loads. A corrupt selected snapshot fails startup visibly and is preserved for investigation. A missing/mismatched revision journal keeps the RDF but starts a fresh local revision counter.
- To transfer a model, download Turtle and copy it to the destination, then start with `BLDGTS_MODEL_PATH=/absolute/path/to/transferred.ttl` and a fresh, isolated `BLDGTS_SNAPSHOT_PATH`. A newer pre-existing snapshot would otherwise take precedence. Parsing is explicitly Turtle, regardless of the filename suffix.
- Mutations schedule background snapshots. Crash recovery restores the **last completed snapshot**; an edit still waiting to be flushed can be lost in an abrupt crash. Call `/api/model/flush` before making a handoff/export checkpoint when durable completion matters.
- Turtle preserves semantic metadata and opaque timeseries links; historian samples live in the store. Transfer or reconnect the store separately. Reference targets remain stable; do not generate replacement timeseries IDs on import.

## Sources

- [Haystack Points](https://project-haystack.org/doc/docHaystack/Points): containment, function, kind, units, history.
- [Haystack Equips](https://project-haystack.org/doc/docHaystack/Equips): site and equipment containment.
- [Haystack Sites](https://project-haystack.org/doc/docHaystack/Sites): site semantics and enrichment.
- [Haystack hisMode](https://project-haystack.org/doc/lib-phIoT/hisMode): exact value enumeration.
- Vendored `data/haystack/defs.json` (4.0.0), used offline at runtime. No live documentation fetch occurs during validation.
