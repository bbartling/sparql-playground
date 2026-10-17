import React, { useMemo, useState } from 'react'

type PlanTriple = { s: string; p: string; o: string; o_kind: string }
type PlanIssue = { severity: string; tag: string; message: string }
type PlanEntity = { iri: string; id: string; status: string; issues?: PlanIssue[] }
type PlanResponse = {
  ok: boolean
  plan_id: string
  plan_hash: string
  base_revision: number
  expires_at: number
  scope_iris: string[]
  affected_iris: string[]
  added: PlanTriple[]
  deleted: PlanTriple[]
  before: { status: string; error_count: number; warn_count: number; entities: PlanEntity[] }
  after: { status: string; error_count: number; warn_count: number; entities: PlanEntity[] }
  revision: number
  error?: string
}

const DEFAULT_UPDATE = `PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX bts: <https://example.org/openfdd/bldgts#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

DELETE DATA {
  bldg:AHU_1_DA_P bts:hasHaystackMarker "sensor" .
}
;
INSERT DATA {
  bldg:AHU_1_DA_P rdfs:label "AHU 1 discharge air pressure" .
  bldg:AHU_1_DA_P bts:hasHaystackMarker "point" .
  bldg:AHU_1_DA_P bts:hasHaystackMarker "sensor" .
  bldg:AHU_1_DA_P bts:hasHaystackMarker "discharge" .
  bldg:AHU_1_DA_P bts:hasHaystackMarker "air" .
  bldg:AHU_1_DA_P bts:hasHaystackMarker "pressure" .
  bldg:AHU_1_DA_P bts:hasHaystackTag _:t1 .
  _:t1 bts:tagName "kind" ; bts:tagKind "Str" ; bts:tagValue "Number" .
  bldg:AHU_1_DA_P bts:hasHaystackTag _:t2 .
  _:t2 bts:tagName "siteRef" ; bts:tagKind "Ref" ; bts:tagValue bldg:Building_50 .
  bldg:AHU_1_DA_P bts:hasHaystackTag _:t3 .
  _:t3 bts:tagName "equipRef" ; bts:tagKind "Ref" ; bts:tagValue bldg:AHU_1 .
}
`

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: response.statusText }))
    const detail = data.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.error || JSON.stringify(detail) || response.statusText
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

function shortIri(value: string): string {
  if (value.includes('#')) return value.split('#').pop() || value
  return value
}

export function AgentPanel(props: {
  revision: number
  allowMutations: boolean
  onApplied: (revision: number) => void
}) {
  const [scopeText, setScopeText] = useState('AHU_1_DA_P')
  const [updateText, setUpdateText] = useState(DEFAULT_UPDATE)
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')

  const scopeIris = useMemo(
    () =>
      scopeText
        .split(/[\s,]+/)
        .map((part) => part.trim())
        .filter(Boolean),
    [scopeText],
  )

  const buildPlan = async () => {
    setBusy(true)
    setError('')
    setNote('')
    setPlan(null)
    try {
      const body = await api<PlanResponse>('/api/agent/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          update: updateText,
          scope_iris: scopeIris,
          expected_revision: props.revision,
        }),
      })
      setPlan(body)
      setNote(`Plan ready · expires ${new Date(body.expires_at * 1000).toLocaleTimeString()}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Plan failed')
    } finally {
      setBusy(false)
    }
  }

  const applyPlan = async () => {
    if (!plan || !props.allowMutations) return
    setBusy(true)
    setError('')
    try {
      const body = await api<{ revision: number }>('/api/agent/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan_id: plan.plan_id,
          plan_hash: plan.plan_hash,
          expected_revision: props.revision,
        }),
      })
      setNote(`Applied · model rev ${body.revision}`)
      setPlan(null)
      props.onApplied(body.revision)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Apply failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="sparql-page agent-page">
      <div className="status-bar status-edit" role="status">
        <span className="status-dot" aria-hidden />
        <strong>SPARQL agent plan</strong>
        <span>Read-only discovery stays on /api/sparql · writes use plan → apply only</span>
      </div>
      <section className="selected-card sparql-card">
        <div className="actions-label">Scope + UPDATE</div>
        <p className="empty-hint">
          Ground <code>DELETE DATA</code> / <code>INSERT DATA</code> only. Scope locks which entity
          IRIs may change. Timeseries refs and ontology triples are rejected.
        </p>
        <label className="field-label">
          Scope (local ids or IRIs)
          <input
            value={scopeText}
            onChange={(event) => setScopeText(event.target.value)}
            disabled={busy}
            placeholder="AHU_1_DA_P"
          />
        </label>
        <textarea
          className="sparql-editor"
          value={updateText}
          onChange={(event) => setUpdateText(event.target.value)}
          rows={16}
          spellCheck={false}
          disabled={busy}
          aria-label="SPARQL UPDATE"
        />
        <div className="editor-controls">
          <button type="button" className="primary-sm" disabled={busy || !scopeIris.length} onClick={() => void buildPlan()}>
            {busy ? 'Working…' : 'Build plan'}
          </button>
          <button
            type="button"
            className="primary-sm"
            disabled={busy || !plan || !props.allowMutations}
            onClick={() => void applyPlan()}
          >
            Apply plan
          </button>
        </div>
        {error ? <p className="sparql-error">{error}</p> : null}
        {note ? <p className="empty-hint">{note}</p> : null}
      </section>

      {plan ? (
        <section className="selected-card sparql-card">
          <div className="actions-label">Review</div>
          <p className="empty-hint">
            plan <code>{plan.plan_id.slice(0, 8)}…</code> · hash <code>{plan.plan_hash.slice(0, 12)}…</code> ·
            base rev {plan.base_revision}
          </p>
          <div className={`status-bar status-${plan.after.status}`} role="status">
            <span className="status-dot" aria-hidden />
            <strong>After profile · {plan.after.status}</strong>
            <span>
              {plan.after.error_count} required · {plan.after.warn_count} recommended (before:{' '}
              {plan.before.status})
            </span>
          </div>
          <h3>Affected</h3>
          <ul className="integrity-list">
            {plan.affected_iris.map((iri) => (
              <li key={iri}>
                <code>{shortIri(iri)}</code>
              </li>
            ))}
          </ul>
          <h3>Deleted ({plan.deleted.length})</h3>
          <pre className="ttl-preview">
            {plan.deleted.map((t) => `${shortIri(t.s)} ${shortIri(t.p)} ${t.o}`).join('\n') || '—'}
          </pre>
          <h3>Added ({plan.added.length})</h3>
          <pre className="ttl-preview">
            {plan.added.map((t) => `${shortIri(t.s)} ${shortIri(t.p)} ${t.o}`).join('\n') || '—'}
          </pre>
          {plan.after.entities.some((entity) => entity.issues?.length) ? (
            <details>
              <summary>Profile issues after apply (preview)</summary>
              <ul className="integrity-list">
                {plan.after.entities.flatMap((entity) =>
                  (entity.issues ?? []).map((issue, index) => (
                    <li key={`${entity.id}-${issue.tag}-${index}`}>
                      <b>
                        {entity.id} · {issue.severity} · {issue.tag}
                      </b>{' '}
                      {issue.message}
                    </li>
                  )),
                )}
              </ul>
            </details>
          ) : null}
        </section>
      ) : null}
    </main>
  )
}
