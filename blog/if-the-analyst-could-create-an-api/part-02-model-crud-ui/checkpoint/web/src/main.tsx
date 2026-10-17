import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { AgentPanel } from './AgentPanel'
import { SparqlPanel } from './SparqlPanel'
import './styles.css'

type Tone = 'green' | 'yellow' | 'red'
type ValueKind = 'Str' | 'Ref' | 'Number' | 'Bool'
type MetadataValue = { kind: ValueKind; value: string | number | boolean }
type Metadata = Record<string, MetadataValue>
type DraftValue = { kind: ValueKind; value: string | boolean }
type Issue = { severity: 'error' | 'warning'; tag: string; message: string }
type TreeNode = {
  id: string; iri: string; name: string; node_type: string
  markers?: string[]; hints?: string[]; complete?: boolean
  status?: Tone; coverage?: Tone; metadata?: Metadata; issues?: Issue[]
  tags: Record<string, string>; children: TreeNode[]
}
type SuggestHit = { symbol: string; score?: number; doc?: string }
type Tab = 'floor' | 'rdf' | 'sparql' | 'agent'
type TagMenu = {
  node: TreeNode; revision: number; token: number; x: number; y: number
  name: string; selected: string[]; metadata: Record<string, DraftValue>
  suggestions: SuggestHit[]; proposal: SuggestHit[]; warnings: string[]; error: string; conflict: boolean
}
const metadataKinds: Record<string, ValueKind> = {
  kind: 'Str', siteRef: 'Ref', equipRef: 'Ref', spaceRef: 'Ref', unit: 'Str', tz: 'Str',
  hisMode: 'Str', enum: 'Str', description: 'Str', precision: 'Number', minVal: 'Number', maxVal: 'Number',
}
const fieldHelp: Record<string, string> = {
  unit: 'Haystack unit symbol, e.g. °C', tz: 'e.g. America/Chicago', enum: 'Comma-separated value labels',
  precision: 'Display decimal places', minVal: 'Minimum value', maxVal: 'Maximum value', curVal: 'Current value',
}
function levelOf(node: TreeNode): string { return node.node_type === 'equipment' ? 'equip' : node.node_type }
class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}
async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: response.statusText }))
    const detail = data.detail
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg ?? JSON.stringify(item)).join('; ')
        : detail?.error || JSON.stringify(detail) || response.statusText
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}
function flatten(nodes: TreeNode[]): TreeNode[] { return nodes.flatMap((node) => [node, ...flatten(node.children)]) }
function branchIds(nodes: TreeNode[]): Set<string> {
  return new Set(flatten(nodes).filter((node) => node.children.length).map((node) => node.id))
}
function rollupCoverage(nodes: TreeNode[]) {
  const records = flatten(nodes)
  const issues = records.flatMap((node) => node.issues ?? [])
  const errors = issues.filter((issue) => issue.severity === 'error').length
  const warnings = issues.filter((issue) => issue.severity === 'warning').length
  const tones = records.map((node) => node.coverage ?? node.status)
  const status: Tone = tones.includes('red') ? 'red' : tones.includes('yellow') ? 'yellow' : 'green'
  return { status, errors, warnings, total: records.length }
}
function draftMetadata(metadata: Metadata = {}): Record<string, DraftValue> {
  return Object.fromEntries(Object.entries(metadata).filter(([key]) => key !== 'dis')
    .map(([key, item]) => [key, { kind: item.kind, value: item.kind === 'Bool' ? item.value === true : String(item.value) }]))
}
function hasChanges(menu: TagMenu): boolean {
  return menu.name !== menu.node.name ||
    [...menu.selected].sort().join('|') !== [...(menu.node.markers ?? [])].sort().join('|') ||
    JSON.stringify(menu.metadata) !== JSON.stringify(draftMetadata(menu.node.metadata))
}
function MarkerPills({ markers }: { markers: string[] }) {
  if (!markers.length) return <span className="pill none">no markers</span>
  return <>{markers.map((marker) => <span key={marker} className="pill custom">{marker}</span>)}</>
}
function DeepTree(props: {
  node: TreeNode; depth: number; editing: boolean; activeId: string | null; expanded: Set<string>
  onToggle: (id: string) => void; onNodeClick: (node: TreeNode, event: React.MouseEvent<HTMLButtonElement>) => void
}) {
  const { node, depth, editing, expanded } = props
  const isOpen = editing || expanded.has(node.id)
  const hasChildren = node.children.length > 0
  const coverage = node.coverage ?? node.status
  return <div><button type="button"
    className={['tree-row', node.node_type === 'point' ? 'item' : 'branch', editing ? 'editable' : '',
      props.activeId === node.id ? 'custom-target' : ''].filter(Boolean).join(' ')}
    style={{ paddingLeft: `${10 + depth * 18}px` }} aria-expanded={hasChildren ? isOpen : undefined}
    aria-haspopup={editing || !hasChildren ? 'dialog' : undefined}
    title={editing ? `Edit or inspect ${node.name}` : hasChildren ? `Expand or collapse ${node.name}` : `Inspect ${node.name}`}
    onClick={(event) => { if (editing || !hasChildren) props.onNodeClick(node, event); else props.onToggle(node.id) }}>
    <span className={`chevron ${hasChildren ? '' : 'placeholder'} ${editing ? 'locked' : ''}`} aria-hidden
      style={{ transform: hasChildren && isOpen ? 'rotate(90deg)' : undefined }}>{hasChildren ? '▸' : '·'}</span>
    <span className="node-copy"><span className="node-name">{node.name}</span><span className="node-meta">{node.node_type}</span></span>
    <span className="pill-stack"><MarkerPills markers={node.markers ?? []} />
      {Object.keys(node.metadata ?? {}).filter((key) => key !== 'dis').length > 0 &&
        <span className="pill none">+{Object.keys(node.metadata ?? {}).filter((key) => key !== 'dis').length} values</span>}</span>
    {!editing && coverage && <span className={`coverage-chip ${coverage}`} role="img" aria-label={`${coverage} model checks${hasChildren ? ', includes descendants' : ''}`} />}
  </button>{hasChildren && isOpen && node.children.map((child) => <DeepTree key={child.iri} {...props} node={child} depth={depth + 1} />)}</div>
}
function MetadataInput(props: { tag: string; item: DraftValue; records: TreeNode[]; disabled: boolean; onChange: (value: string | boolean) => void }) {
  const { tag, item, disabled, onChange } = props
  const common = { 'aria-label': `${tag} value`, disabled }
  if (item.kind === 'Bool') return <select {...common} value={String(item.value)} onChange={(event) => onChange(event.target.value === 'true')}>
    <option value="true">true</option><option value="false">false</option></select>
  if (item.kind === 'Ref') {
    const records = props.records.filter((node) => {
      if (node.id === String(item.value)) return true
      if (tag === 'siteRef') return ['site', 'building'].includes(node.node_type)
      if (tag === 'equipRef') return ['equipment', 'part'].includes(node.node_type)
      if (tag === 'spaceRef') return ['space', 'floor', 'zone'].includes(node.node_type)
      return true
    })
    return <select {...common} value={String(item.value)} onChange={(event) => onChange(event.target.value)}>
      <option value="">Choose a record…</option>
      {!records.some((node) => node.id === String(item.value)) && item.value && <option value={String(item.value)}>{String(item.value)} (unresolved)</option>}
      {records.map((node) => <option key={node.id} value={node.id}>{node.name} · {node.id}</option>)}</select>
  }
  const choices = tag === 'kind' ? ['Number', 'Bool', 'Str'] : tag === 'hisMode' ? ['sampled', 'cov', 'consumption'] : null
  if (choices) return <select {...common} value={String(item.value)} onChange={(event) => onChange(event.target.value)}>
    <option value="">Choose…</option>{item.value && !choices.includes(String(item.value)) && <option value={String(item.value)}>{String(item.value)}</option>}
    {choices.map((choice) => <option key={choice}>{choice}</option>)}</select>
  return <input {...common} type={item.kind === 'Number' ? 'number' : 'text'} step={item.kind === 'Number' ? 'any' : undefined}
    placeholder={fieldHelp[tag]} value={String(item.value)} onChange={(event) => onChange(event.target.value)} />
}
function App() {
  const [tab, setTab] = useState<Tab>('floor')
  const [tree, setTree] = useState<TreeNode[]>([])
  const [revision, setRevision] = useState(0)
  const [allowMutations, setAllowMutations] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState(false)
  const [menu, setMenu] = useState<TagMenu | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [ttlText, setTtlText] = useState('')
  const [ttlBusy, setTtlBusy] = useState(false)
  const [markerQuery, setMarkerQuery] = useState('')
  const [newTag, setNewTag] = useState('kind')
  const [newKind, setNewKind] = useState<ValueKind>('Str')
  const [validationOpen, setValidationOpen] = useState(false)
  const [savedName, setSavedName] = useState('')
  const [validationProfile, setValidationProfile] = useState('Application Haystack core profile')
  const [validationLimits, setValidationLimits] = useState<string[]>([])
  const markerQueryRef = useRef(markerQuery)
  markerQueryRef.current = markerQuery
  const menuRef = useRef<HTMLDivElement | null>(null)
  const triggerRef = useRef<HTMLElement | null>(null)
  const requestToken = useRef(0)
  const menuState = useRef(menu)
  const busyState = useRef(busy)
  menuState.current = menu; busyState.current = busy
  const coverage = useMemo(() => rollupCoverage(tree), [tree])
  const records = useMemo(() => flatten(tree), [tree])
  const canEdit = allowMutations && editing
  const loadTree = async () => {
    setLoading(true)
    try {
      const body = await api<{ revision: number; allow_mutations: boolean; tree: TreeNode[]; validation_profile?: string; validation_limits?: string[] }>('/api/model/tree')
      setTree(body.tree); setRevision(body.revision); setAllowMutations(body.allow_mutations)
      setValidationProfile(body.validation_profile ?? 'Application Haystack core profile'); setValidationLimits(body.validation_limits ?? [])
      setExpanded((current) => current.size > 0 ? current : branchIds(body.tree))
      return body
    } finally { setLoading(false) }
  }
  const loadTtl = async () => {
    setTtlBusy(true)
    try {
      const response = await fetch('/api/model/ttl?scope=model')
      if (!response.ok) throw new Error(`TTL ${response.status}`)
      setTtlText(await response.text())
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to load Turtle') }
    finally { setTtlBusy(false) }
  }
  const closeMenu = () => { if (!busyState.current) { setMenu(null); triggerRef.current?.focus() } }
  useEffect(() => { loadTree().catch((err: Error) => setError(err.message)) }, [])
  useEffect(() => { if (tab === 'rdf') void loadTtl() }, [tab, revision])
  useEffect(() => {
    if (!menu) return
    const frame = requestAnimationFrame(() => {
      const popup = menuRef.current
      if (!popup) return
      const bounds = popup.getBoundingClientRect()
      setMenu((current) => current?.token === menu.token ? { ...current,
        x: Math.max(8, Math.min(current.x, window.innerWidth - bounds.width - 8)),
        y: Math.max(8, Math.min(current.y, window.innerHeight - bounds.height - 8)),
      } : current)
      popup.querySelector<HTMLElement>('input:not(:disabled), button:not(:disabled), select:not(:disabled)')?.focus()
    })
    const onDoc = (event: MouseEvent) => {
      const current = menuState.current
      if (current && menuRef.current && !menuRef.current.contains(event.target as Node) && !hasChanges(current) && !busyState.current) closeMenu()
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); closeMenu(); return }
      if (event.key !== 'Tab' || !menuRef.current) return
      const focusable = Array.from(menuRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, [tabindex="0"]'))
      const first = focusable[0]; const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('mousedown', onDoc); document.addEventListener('keydown', onKey)
    return () => { cancelAnimationFrame(frame); document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey) }
  }, [menu?.token])
  const openTagMenu = async (node: TreeNode, event: React.MouseEvent<HTMLButtonElement>) => {
    if (busy) return
    triggerRef.current = event.currentTarget
    const bounds = event.currentTarget.getBoundingClientRect()
    const token = ++requestToken.current
    setMarkerQuery(''); setNewTag('kind'); setNewKind('Str')
    setMenu({ node, revision, token, x: Math.max(8, Math.min(event.clientX || bounds.left + 24, window.innerWidth - 438)),
      y: Math.max(8, Math.min(event.clientY || bounds.bottom, window.innerHeight - 620)),
      name: node.name, selected: [...(node.markers ?? [])], metadata: draftMetadata(node.metadata),
      suggestions: (node.hints ?? []).map((symbol) => ({ symbol })), proposal: (node.hints ?? []).map((symbol) => ({ symbol })), warnings: [], error: '', conflict: false })
    if (!canEdit) return
    try {
      const [guess, suggest] = await Promise.all([
        api<{ markers: string[]; warnings?: string[] }>(`/api/model/haystack/guess?q=${encodeURIComponent(node.name)}&level=${encodeURIComponent(levelOf(node))}`),
        api<{ suggestions: SuggestHit[] }>(`/api/model/haystack/suggest?q=${encodeURIComponent(node.name)}&level=${encodeURIComponent(levelOf(node))}&n=12`),
      ])
      const hits = [...(guess.markers ?? []).map((symbol) => ({ symbol })), ...(suggest.suggestions ?? [])]
      const suggestions = [...new Map(hits.map((hit) => [hit.symbol, hit])).values()]
      setMenu((current) => current?.token === token ? { ...current, proposal: suggestions, suggestions: markerQueryRef.current.trim() ? current.suggestions : suggestions, warnings: guess.warnings ?? [] } : current)
    } catch (err) {
      setMenu((current) => current?.token === token ? { ...current, error: `Suggestions unavailable: ${err instanceof Error ? err.message : 'request failed'}` } : current)
    }
  }
  useEffect(() => {
    if (!menu || !canEdit) return
    if (!markerQuery.trim()) { setMenu((current) => current ? { ...current, suggestions: current.proposal } : current); return }
    const token = menu.token
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      api<{ suggestions: SuggestHit[] }>(`/api/model/haystack/suggest?q=${encodeURIComponent(markerQuery)}&level=${encodeURIComponent(levelOf(menu.node))}&n=20`, { signal: controller.signal })
        .then((body) => setMenu((current) => current?.token === token ? { ...current, suggestions: body.suggestions } : current))
        .catch((err: Error) => { if (err.name !== 'AbortError') setMenu((current) => current?.token === token ? { ...current, error: err.message } : current) })
    }, 220)
    return () => { clearTimeout(timer); controller.abort() }
  }, [markerQuery, menu?.token, canEdit])
  const toggleSelected = (symbol: string) => setMenu((current) => current ? { ...current, selected: current.selected.includes(symbol)
    ? current.selected.filter((marker) => marker !== symbol) : [...current.selected, symbol] } : current)
  const updateMetadata = (tag: string, item: DraftValue) => setMenu((current) => current
    ? { ...current, metadata: { ...current.metadata, [tag]: item }, error: '' } : current)
  const addMetadata = () => {
    const tag = newTag.trim()
    if (!menu || !tag) return
    if (!/^[a-z][a-zA-Z0-9]*$/.test(tag) || tag === 'dis') {
      setMenu({ ...menu, error: 'Use a camelCase tag name. Edit dis with the Display name field.' }); return
    }
    if (menu.metadata[tag]) { setMenu({ ...menu, error: `${tag} is already in this record.` }); return }
    const kind = metadataKinds[tag] ?? newKind
    updateMetadata(tag, { kind, value: kind === 'Bool' ? false : '' }); setNewTag('')
  }
  const saveRecord = async () => {
    if (!menu || busy || !canEdit) return
    try {
      if (!menu.name.trim()) throw new Error('Display name cannot be empty.')
      const metadata: Metadata = { dis: { kind: 'Str', value: menu.name.trim() } }
      for (const [tag, item] of Object.entries(menu.metadata)) {
        if (item.kind === 'Number') {
          if (String(item.value).trim() === '' || !Number.isFinite(Number(item.value))) throw new Error(`${tag} needs a finite number.`)
          metadata[tag] = { kind: 'Number', value: Number(item.value) }
        } else {
          if (item.kind === 'Ref' && !item.value) throw new Error(`Choose a record for ${tag}, or remove the tag.`)
          metadata[tag] = { kind: item.kind, value: item.value }
        }
      }
      setBusy(true); setMenu((current) => current ? { ...current, error: '' } : current)
      const body = await api<{ revision: number }>('/api/model/metadata', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: [{ entity_id: menu.node.id, markers: menu.selected, metadata }], expected_revision: menu.revision }),
      })
      setRevision(body.revision); setSavedName(menu.name.trim()); setValidationOpen(false)
      // The write is committed even if refresh fails; never retry against the old revision.
      setMenu(null); triggerRef.current?.focus()
      try { await loadTree() } catch (err) { setError(`Saved successfully. Tree refresh failed: ${err instanceof Error ? err.message : 'request failed'}`) }
    } catch (err) {
      setMenu((current) => current ? { ...current, error: err instanceof Error ? err.message : 'Save failed',
        conflict: err instanceof ApiError && err.status === 409 } : current)
    } finally { setBusy(false) }
  }
  const reloadRecord = async () => {
    if (!menu || busy) return
    setBusy(true)
    try {
      const body = await loadTree()
      const fresh = flatten(body.tree).find((node) => node.id === menu.node.id)
      if (!fresh) throw new Error('This record was removed. Close the editor and refresh the model.')
      setMenu({ ...menu, node: fresh, revision: body.revision, name: fresh.name, selected: [...(fresh.markers ?? [])],
        metadata: draftMetadata(fresh.metadata), error: '', conflict: false })
    } catch (err) { setMenu((current) => current ? { ...current, error: err instanceof Error ? err.message : 'Refresh failed' } : current) }
    finally { setBusy(false) }
  }
  const coverageTitle = coverage.status === 'green' ? 'Haystack checks passed'
    : coverage.status === 'yellow' ? 'Haystack recommendations' : 'Haystack requirements missing'
  const dirty = menu ? hasChanges(menu) : false
  const metadataEntries = menu ? Object.entries(menu.metadata) : []
  const showValidation = !editing || !!savedName
  return <div className="app">
    <header className="topbar"><div className="brand"><div className="brand-mark">HS</div>
      <div className="brand-copy"><h1>Haystack model editor</h1><p>Edit · click any record · review tags and values · save</p></div></div>
      <div className="top-actions"><span className="pill none">rev {revision}</span><span className={allowMutations ? 'pill received' : 'pill none'}>{allowMutations ? 'mutations on' : 'read-only'}</span></div>
    </header>
    <nav className="tabs" aria-label="Model views">{([['floor', 'Model'], ['sparql', 'SPARQL'], ['agent', 'Agent'], ['rdf', 'RDF']] as const).map(([id, label]) =>
      <button key={id} className={tab === id ? 'tab active' : 'tab'} aria-current={tab === id ? 'page' : undefined} type="button"
        onClick={() => { setTab(id); setMenu(null) }} disabled={busy}>{label}</button>)}</nav>
    {tab === 'sparql' ? <SparqlPanel revision={revision} /> : tab === 'agent' ? <AgentPanel revision={revision} allowMutations={allowMutations}
      onApplied={(next) => { setRevision(next); void loadTree().catch((err: Error) => setError(err.message)) }} />
    : tab === 'rdf' ? <main className="dashboard">
      <section className="panel" style={{ padding: 0, minHeight: 0, flex: 1 }}><div className="panel-head"><div><h2>Live RDF (Turtle)</h2><span>GET /api/model/ttl</span></div>
        <button type="button" className="ghost" onClick={() => void loadTtl()} disabled={ttlBusy}>Refresh</button></div>
        <pre className="rdf-raw">{ttlBusy && !ttlText ? 'Loading…' : ttlText}</pre></section></main>
      : <main className="workspace tree-only"><section className={`panel tree-panel tree-panel-full ${editing ? 'is-editing' : ''}`}>
        {tree.length > 0 && <><div className={`status-bar ${showValidation ? `status-${coverage.status}` : 'status-edit'}`} role="status">
          <span className="status-dot" aria-hidden /><strong>{showValidation ? `${savedName ? 'Saved · ' : ''}${coverageTitle}` : allowMutations ? 'Edit mode' : 'Inspect mode'}</strong>
          <span>{showValidation ? `${coverage.errors} required errors · ${coverage.warnings} recommendations` : allowMutations ? 'Names, tags and values · checks after Save' : 'Select a record to inspect saved tags and values'}</span>
          <button type="button" className="validation-toggle" aria-label={validationOpen ? 'Hide saved model checks' : 'Show saved model checks'} aria-expanded={validationOpen} onClick={() => setValidationOpen(!validationOpen)}>
            {validationOpen ? 'Hide checks' : 'Show checks'}</button></div>
          {validationOpen && <div className="validation-results"><p><strong>Supported Haystack profile</strong> · {validationProfile}</p><p>Saved model · red: required metadata · yellow: recommendations · green: these checks pass.</p>
            {records.filter((node) => (node.issues ?? []).length).map((node) => <details key={node.id}><summary>{node.name} <span className={`check-tone ${node.status}`}>{node.status}</span></summary>
              <ul className="editor-issues">{node.issues!.map((issue, index) => <li className={issue.severity} key={`${issue.tag}-${index}`}>
                <strong>{issue.severity === 'error' ? 'Required' : 'Recommended'} · {issue.tag}</strong><span>{issue.message}</span></li>)}</ul></details>)}
            {!coverage.errors && !coverage.warnings && <p>No errors or recommendations from the current checks.</p>}
            {!!validationLimits.length && <details><summary>What these checks cover</summary><ul>{validationLimits.map((limit) => <li key={limit}>{limit}</li>)}</ul></details>}</div>}</>}
        <div className="panel-head"><div><h2>Building tree</h2><span>{editing ? `Locked · click any record to ${allowMutations ? 'edit' : 'inspect'}` : `Scroll the tree · ${allowMutations ? 'Edit' : 'Inspect'} any record`}</span></div>
          <div className="edit-controls"><button type="button" className="ghost" disabled={busy || loading} onClick={() => void loadTree().catch((err: Error) => setError(err.message))}>{loading ? 'Loading…' : 'Refresh'}</button>
            <button type="button" className={editing ? 'ghost' : 'primary-sm'} disabled={busy || !tree.length}
              onClick={() => { setExpanded(branchIds(tree)); setEditing(!editing); setMenu(null); setSavedName(''); setValidationOpen(false) }}>{editing ? 'Done' : allowMutations ? 'Edit' : 'Inspect'}</button></div></div>
        <div className="tree-scroll" aria-label="Building model records" aria-busy={loading}>
          {!tree.length && <p className="tree-empty">{loading ? 'Loading the building model…' : 'No model records loaded. Refresh to try again.'}</p>}
          {tree.map((node) => <DeepTree key={node.iri} node={node} depth={0} editing={editing} activeId={menu?.node.id ?? null} expanded={expanded}
            onToggle={(id) => setExpanded((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next })}
            onNodeClick={(item, event) => { setSavedName(''); void openTagMenu(item, event) }} />)}
        </div></section></main>}
    {menu && <div ref={menuRef} className="tag-menu record-editor" style={{ left: menu.x, top: menu.y }} role="dialog" aria-modal="true"
      aria-labelledby="record-editor-title" aria-describedby="record-editor-id" aria-busy={busy}>
      <div className="tag-menu-head editor-head"><div><strong id="record-editor-title">{canEdit ? 'Edit record' : 'Inspect record'}</strong>
        <span className="record-id" id="record-editor-id" title={menu.node.iri}>{menu.node.node_type} · {menu.node.id}</span></div>
        <button type="button" className="close-editor" aria-label="Close editor" onClick={closeMenu} disabled={busy}>×</button></div>
      <div className="editor-scroll"><label className="editor-field"><span>Display name <code>dis · Str</code></span>
        <input value={menu.name} disabled={!canEdit || busy} onChange={(event) => setMenu({ ...menu, name: event.target.value })} /></label>
        <p className="editor-note">The record ID and timeseries link stay stable when you rename it.</p>
        <section className="editor-section"><h3>Marker tags <span>{menu.selected.length}</span></h3>
          <div className="tag-menu-chips selected-markers">{menu.selected.length ? menu.selected.map((symbol) =>
            <button key={symbol} type="button" className="preset-chip is-active" aria-label={`Remove marker ${symbol}`} onClick={() => toggleSelected(symbol)} disabled={!canEdit || busy}>{symbol}<span aria-hidden> ×</span></button>) : <p className="editor-note">No marker tags saved.</p>}</div>
          {canEdit && <><label className="editor-field"><span>Find a Haystack marker</span><input placeholder="Search the marker catalog…" value={markerQuery} disabled={busy} onChange={(event) => setMarkerQuery(event.target.value)} /></label>
            <p className="editor-note">{markerQuery ? 'Catalog matches' : 'Fuzzy suggestions'} · click to add; review before saving.</p>
            <div className="tag-menu-chips suggested-markers">{menu.suggestions.filter((hit) => !menu.selected.includes(hit.symbol)).map((hit) =>
              <button key={hit.symbol} type="button" className="preset-chip" title={hit.doc ?? 'Suggested marker; review before adding'} aria-label={`Add marker ${hit.symbol}`} disabled={busy} onClick={() => toggleSelected(hit.symbol)}>+ {hit.symbol}</button>)}</div>
            {!!menu.warnings.length && <details className="suggestion-notes"><summary>Suggestion notes</summary><ul>{menu.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></details>}</>}
        </section>
        <section className="editor-section"><h3>Values & references <span>{metadataEntries.length}</span></h3>
          {metadataEntries.map(([tag, item]) => <div className="metadata-row" key={tag}>
            <div className="metadata-label"><label htmlFor={`metadata-${tag}`}>{tag}</label><select id={`metadata-${tag}`} aria-label={`${tag} value type`} value={item.kind}
              disabled={!canEdit || busy || !!metadataKinds[tag]} onChange={(event) => updateMetadata(tag, { kind: event.target.value as ValueKind, value: event.target.value === 'Bool' ? false : '' })}>
              {(['Str', 'Ref', 'Number', 'Bool'] as const).map((kind) => <option key={kind}>{kind}</option>)}</select></div>
            <MetadataInput tag={tag} item={item} records={records} disabled={!canEdit || busy} onChange={(value) => updateMetadata(tag, { ...item, value })} />
            {canEdit && <button type="button" className="remove-field" aria-label={`Remove metadata ${tag}`} disabled={busy} onClick={() => setMenu((current) => {
              if (!current) return current
              const next = { ...current.metadata }; delete next[tag]; return { ...current, metadata: next }
            })}>×</button>}</div>)}
          {!metadataEntries.length && <p className="editor-note">No value or reference tags saved.</p>}
          {canEdit && <div className="add-metadata"><input list="metadata-tags" aria-label="Metadata tag name" placeholder="Tag name…" value={newTag} disabled={busy}
            onChange={(event) => { setNewTag(event.target.value); setNewKind(metadataKinds[event.target.value] ?? 'Str') }} />
            <datalist id="metadata-tags">{Object.keys(metadataKinds).concat('curVal').filter((tag) => !menu.metadata[tag]).map((tag) => <option key={tag} value={tag} />)}</datalist>
            <select aria-label="New metadata value type" value={metadataKinds[newTag] ?? newKind} disabled={busy || !!metadataKinds[newTag]} onChange={(event) => setNewKind(event.target.value as ValueKind)}>
              {(['Str', 'Ref', 'Number', 'Bool'] as const).map((kind) => <option key={kind}>{kind}</option>)}</select>
            <button type="button" className="ghost tiny" disabled={busy || !newTag.trim()} onClick={addMetadata}>+ Add</button></div>}
        </section>
        {Object.keys(menu.node.tags ?? {}).length > 0 && <details className="record-links"><summary>Storage links</summary><dl>{Object.entries(menu.node.tags).map(([tag, value]) =>
          <React.Fragment key={tag}><dt>{tag}</dt><dd>{value}</dd></React.Fragment>)}</dl></details>}
        {menu.error && <div className="editor-error" role="alert">{menu.error}{menu.conflict && <><p>Another editor changed the model. Your draft has been kept.</p>
          <button type="button" className="ghost tiny" onClick={() => void reloadRecord()} disabled={busy}>Discard draft & reload latest</button></>}</div>}
      </div>
      <div className="tag-menu-actions"><span className="draft-state">{busy ? 'Saving…' : dirty ? 'Unsaved draft' : `rev ${menu.revision}`}</span>
        <button type="button" className="ghost tiny" onClick={closeMenu} disabled={busy}>{dirty ? 'Discard' : 'Close'}</button>
        {canEdit && <button type="button" className="primary-sm" onClick={() => void saveRecord()} disabled={busy || !dirty || menu.conflict}>Save</button>}</div>
    </div>}
    {error && <div className="toast error" role="alert">{error}<button type="button" aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}
  </div>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
