import React, { useCallback, useEffect, useMemo, useState } from 'react'

type SparqlBinding = Record<string, { type?: string; value?: string }>
type SparqlResults = {
  head?: { vars?: string[] }
  results?: { bindings?: SparqlBinding[] }
  boolean?: boolean
}

const DEFAULT_QUERY = `PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?ahu ?label WHERE {
  ?ahu a/(rdfs:subClassOf|owl:equivalentClass)* brick:Air_Handler_Unit .
  FILTER(STRSTARTS(STR(?ahu), STR(bldg:)))
  OPTIONAL { ?ahu rdfs:label ?label }
}
ORDER BY ?ahu
`

const PRESETS: Array<{ label: string; example: string }> = [
  { label: 'AHUs', example: '01_list_ahus.rq' },
  { label: 'Mech summary', example: '01_mech_summary.rq' },
  { label: 'Point tags', example: '01_point_tags.rq' },
  { label: 'FC1 points', example: '02_fc1_points.rq' },
]

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: response.statusText }))
    const detail = data.detail
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return response.json() as Promise<T>
}

type IntegrityIssue = {
  check: string
  message: string
  count: number
  severity: string
  samples?: string[] | null
}

type IntegrityReport = {
  status: 'green' | 'yellow' | 'red'
  error_count: number
  warn_count: number
  issues: IntegrityIssue[]
}

export function SparqlPanel({ revision = 0 }: { revision?: number }) {
  const [examples, setExamples] = useState<string[]>([])
  const [selectedExample, setSelectedExample] = useState('')
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [running, setRunning] = useState(false)
  const [sparqlErr, setSparqlErr] = useState('')
  const [sparqlMeta, setSparqlMeta] = useState<Record<string, unknown> | null>(null)
  const [sparqlBody, setSparqlBody] = useState<SparqlResults | null>(null)
  const [drillPoint, setDrillPoint] = useState<string | null>(null)
  const [drillMsg, setDrillMsg] = useState('')
  const [drillSamples, setDrillSamples] = useState<Array<{ ts: string; value: number }>>([])
  const [ttlMsg, setTtlMsg] = useState('')
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null)

  useEffect(() => {
    api<{ examples: string[] }>('/api/sparql/examples')
      .then((j) => setExamples(j.examples || []))
      .catch((e) => setSparqlErr(String(e)))
  }, [])

  useEffect(() => {
    api<IntegrityReport>('/api/model/integrity')
      .then((j) => setIntegrity(j))
      .catch(() => setIntegrity(null))
  }, [revision])
  const loadExample = useCallback(async (name: string) => {
    if (!name) return null
    try {
      const j = await api<{ query: string }>(`/api/sparql/examples/${encodeURIComponent(name)}`)
      setQuery(j.query)
      setSelectedExample(name)
      setSparqlErr('')
      return j.query
    } catch (e) {
      setSparqlErr(String(e))
      return null
    }
  }, [])

  async function runSparql(queryOverride?: string) {
    const q = queryOverride ?? query
    setRunning(true)
    setSparqlErr('')
    setSparqlBody(null)
    setSparqlMeta(null)
    setDrillPoint(null)
    setDrillSamples([])
    try {
      const j = await api<{
        results?: SparqlResults
        meta?: Record<string, unknown>
      }>('/api/sparql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      })
      setSparqlBody(j.results || null)
      setSparqlMeta(j.meta || null)
    } catch (e) {
      setSparqlErr(String(e))
    } finally {
      setRunning(false)
    }
  }

  async function applyPreset(example: string) {
    const q = await loadExample(example)
    if (q) await runSparql(q)
  }

  async function drillPointHistory(pointId: string) {
    setDrillPoint(pointId)
    setDrillMsg('Loading…')
    setDrillSamples([])
    try {
      const j = await api<{
        timeseries_id?: string
        samples?: Array<{ ts: string; value: number }>
        truncated?: boolean
      }>(`/api/points/${encodeURIComponent(pointId)}/timeseries?limit=50`)
      setDrillSamples(j.samples || [])
      setDrillMsg(
        [
          `ts id=${j.timeseries_id || '—'}`,
          `${(j.samples || []).length} samples`,
          j.truncated ? 'truncated' : '',
        ]
          .filter(Boolean)
          .join(' · '),
      )
    } catch (e) {
      setDrillMsg(String(e))
    }
  }

  async function downloadTtl() {
    try {
      const r = await fetch('/api/model/ttl')
      const text = await r.text()
      if (!r.ok) throw new Error(text)
      const blob = new Blob([text], { type: 'text/turtle;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'building.ttl'
      a.click()
      URL.revokeObjectURL(url)
      setTtlMsg('Downloaded building.ttl (also written at repo root on the server)')
    } catch (e) {
      setTtlMsg(String(e))
    }
  }

  const vars = useMemo(() => sparqlBody?.head?.vars || [], [sparqlBody])
  const bindings = useMemo(() => sparqlBody?.results?.bindings || [], [sparqlBody])
  const pointIdVar = vars.find(
    (v) =>
      v.toLowerCase() === 'point' ||
      v.toLowerCase() === 'pointid' ||
      v.toLowerCase() === 'point_id',
  )

  const tone = integrity?.status ?? 'yellow'
  const integrityTitle =
    tone === 'green'
      ? 'RDF model healthy'
      : tone === 'yellow'
        ? 'RDF warnings'
        : 'RDF model problems'
  const integrityDetail = integrity
    ? `${integrity.error_count} error(s) · ${integrity.warn_count} warning(s)`
    : 'Checking model…'

  return (
    <main className="sparql-page">
      <div className={`status-bar status-${tone}`} role="status">
        <span className="status-dot" aria-hidden />
        <strong>{integrityTitle}</strong>
        <span>{integrityDetail}</span>
      </div>
      {integrity?.issues?.length ? (
        <ul className="integrity-list">
          {integrity.issues.slice(0, 8).map((issue) => (
            <li key={issue.check}>
              <b>{issue.check}</b> · {issue.message}
              {issue.samples?.length ? ` · e.g. ${issue.samples.slice(0, 3).join(', ')}` : ''}
            </li>
          ))}
        </ul>
      ) : null}

      <section className="selected-card sparql-card">
        <div className="actions-label">SPARQL editor</div>
        <p className="empty-hint">
          Read-only SELECT/ASK against the live model graph. Presets load tutorial `.rq` files from
          the repo, then run them in the browser.
        </p>

        <div className="preset-chips" role="group" aria-label="Tutorial presets">
          {PRESETS.map((p) => (
            <button
              key={p.example}
              type="button"
              className={`preset-chip${selectedExample === p.example ? ' is-active' : ''}`}
              disabled={running}
              onClick={() => void applyPreset(p.example)}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="editor-controls">
          <label className="field-label">
            Example file
            <select
              value={selectedExample}
              onChange={(e) => {
                const v = e.target.value
                setSelectedExample(v)
                void loadExample(v)
              }}
            >
              <option value="">— custom —</option>
              {examples.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="primary-sm"
            disabled={running}
            onClick={() => void runSparql()}
          >
            {running ? 'Running…' : 'Run query'}
          </button>
        </div>

        <textarea
          className="sparql-editor"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={14}
          spellCheck={false}
          aria-label="SPARQL query"
        />

        {sparqlErr ? <p className="sparql-error">{sparqlErr}</p> : null}
        {sparqlMeta ? (
          <p className="empty-hint">
            {String(sparqlMeta.row_count ?? bindings.length)} row(s)
            {sparqlMeta.truncated ? ' (truncated)' : ''}
          </p>
        ) : null}
        {typeof sparqlBody?.boolean === 'boolean' ? (
          <p>
            ASK → <strong>{sparqlBody.boolean ? 'true' : 'false'}</strong>
          </p>
        ) : null}

        {vars.length > 0 && bindings.length > 0 ? (
          <div className="table-wrap sparql-table">
            <table>
              <thead>
                <tr>
                  {vars.map((v) => (
                    <th key={v}>{v}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bindings.slice(0, 200).map((row, i) => (
                  <tr key={i}>
                    {vars.map((v) => {
                      const val = row[v]?.value ?? ''
                      const isPoint = pointIdVar === v && Boolean(val)
                      const short =
                        val.startsWith('http') && val.includes('#')
                          ? val.split('#').pop() || val
                          : val
                      return (
                        <td key={v}>
                          {isPoint ? (
                            <button
                              type="button"
                              className="linkish"
                              onClick={() => void drillPointHistory(short || val)}
                              title="Load timeseries samples"
                            >
                              {short}
                            </button>
                          ) : (
                            short
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {drillPoint ? (
          <div className="drill-block">
            <div className="actions-label">Point history · {drillPoint}</div>
            <p className="empty-hint">{drillMsg}</p>
            {drillSamples.length > 0 ? (
              <pre className="ttl-preview">
                {drillSamples
                  .slice(-20)
                  .map((s) => `${s.ts}\t${s.value}`)
                  .join('\n')}
              </pre>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="selected-card sparql-card">
        <div className="actions-label">Turtle export</div>
        <p className="empty-hint">
          Downloads the live model and triggers a background write of repo-root{' '}
          <code>building.ttl</code>.
        </p>
        <button type="button" className="primary-sm" onClick={() => void downloadTtl()}>
          Download building.ttl
        </button>
        {ttlMsg ? <p className="empty-hint">{ttlMsg}</p> : null}
      </section>
    </main>
  )
}
