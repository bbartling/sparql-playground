import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { SparqlPanel } from './SparqlPanel'
import './styles.css'

type TreeNode = {
  id: string
  iri: string
  name: string
  node_type: string
  tags: Record<string, string>
  children: TreeNode[]
}

type PendingDraft = {
  status?: 'received' | 'not_received'
  meta?: string
  note?: string
}

type Tab = 'floor' | 'dashboard' | 'sparql'

const HOLD_MS = 480
const FALLBACK_META: Record<string, string> = {
  LATE: 'Late vs expected window',
  DAMAGED: 'Visible damage',
  SHORT: 'Quantity / coverage short',
  HOLD: 'Hold for QA or review',
  MISSHIP: 'Wrong assignment / mis-wired',
  CUSTOM: 'Freeform note (requires text)',
}

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: response.statusText }))
    const detail = data.detail
    throw new Error(
      typeof detail === 'string'
        ? detail
        : detail?.error || JSON.stringify(detail) || response.statusText,
    )
  }
  return response.json() as Promise<T>
}

function flatten(nodes: TreeNode[]): TreeNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children)])
}

function branchIds(nodes: TreeNode[]): Set<string> {
  const open = new Set<string>()
  const walk = (list: TreeNode[]) => {
    for (const node of list) {
      if (node.children.length > 0) {
        open.add(node.id)
        walk(node.children)
      }
    }
  }
  walk(nodes)
  return open
}

function statusPill(status?: string | null, pending = false) {
  const cls = pending ? 'pill pending' : 'pill'
  if (status === 'received') return <span className={`${cls} received`}>Received</span>
  if (status === 'not_received') return <span className={`${cls} returned`}>Not received</span>
  return <span className={`${cls} none`}>Open</span>
}

function metaPill(meta?: string | null, note?: string | null, pending = false) {
  if (!meta) return null
  const cls = pending ? 'pill pending custom' : 'pill custom'
  return <span className={cls}>{meta === 'CUSTOM' && note ? `CUSTOM: ${note}` : meta}</span>
}

function DeepTree(props: {
  node: TreeNode
  depth: number
  editing: boolean
  lockedOpen: boolean
  pending: Record<string, PendingDraft>
  metaTargetId: string | null
  expanded: Set<string>
  onToggle: (id: string) => void
  onItemLeftClick: (node: TreeNode) => void
  onItemRightClick: (node: TreeNode) => void
  onItemHold: (node: TreeNode) => void
  onSelectOwner: (node: TreeNode) => void
}) {
  const { node, depth, lockedOpen, expanded } = props
  const isOpen = lockedOpen || expanded.has(node.id)
  const hasChildren = node.children.length > 0
  const isPoint = node.node_type === 'point'
  const staged = props.pending[node.id]
  const holdTimer = useRef<number | null>(null)
  const holdFired = useRef(false)
  const clearHold = () => {
    if (holdTimer.current != null) window.clearTimeout(holdTimer.current)
    holdTimer.current = null
  }

  return (
    <div>
      <button
        type="button"
        className={[
          'tree-row',
          isPoint ? 'item' : 'branch',
          staged?.status ? `staged-${staged.status}` : staged?.meta ? 'staged-meta' : '',
          props.metaTargetId === node.id ? 'custom-target' : '',
          props.editing && isPoint ? 'editable' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        style={{ paddingLeft: `${10 + depth * 18}px` }}
        onContextMenu={(event) => {
          if (props.editing && isPoint) {
            event.preventDefault()
            props.onItemRightClick(node)
          }
        }}
        onPointerDown={(event) => {
          if (!props.editing || !isPoint || event.button !== 0) return
          holdFired.current = false
          clearHold()
          holdTimer.current = window.setTimeout(() => {
            holdFired.current = true
            props.onItemHold(node)
          }, HOLD_MS)
        }}
        onPointerUp={clearHold}
        onPointerLeave={clearHold}
        onPointerCancel={clearHold}
        onClick={() => {
          if (props.editing && isPoint) {
            if (holdFired.current) {
              holdFired.current = false
              return
            }
            props.onItemLeftClick(node)
            return
          }
          props.onSelectOwner(node)
          if (hasChildren && !lockedOpen) props.onToggle(node.id)
        }}
      >
        <span
          className={`chevron ${hasChildren ? '' : 'placeholder'} ${lockedOpen ? 'locked' : ''}`}
          style={{ transform: hasChildren && isOpen ? 'rotate(90deg)' : undefined }}
          onClick={(event) => {
            event.stopPropagation()
            if (hasChildren && !lockedOpen) props.onToggle(node.id)
          }}
        >
          {hasChildren ? '▸' : '·'}
        </span>
        <span className="node-copy">
          <span className="node-name">{node.name}</span>
          <span className="node-meta">
            {node.node_type}
            {staged ? ' · pending' : ''}
          </span>
        </span>
        {isPoint && (
          <span className="pill-stack">
            {statusPill(staged?.status ?? node.tags.status, Boolean(staged?.status))}
            {metaPill(
              staged?.meta ?? node.tags.meta,
              staged?.note ?? node.tags.custom,
              Boolean(staged?.meta),
            )}
          </span>
        )}
      </button>
      {hasChildren &&
        isOpen &&
        node.children.map((child) => (
          <DeepTree key={child.iri} {...props} node={child} depth={depth + 1} />
        ))}
    </div>
  )
}

function App() {
  const [tab, setTab] = useState<Tab>('floor')
  const [tree, setTree] = useState<TreeNode[]>([])
  const [revision, setRevision] = useState(0)
  const [allowMutations, setAllowMutations] = useState(false)
  const [metaCatalog, setMetaCatalog] = useState(FALLBACK_META)
  const [dash, setDash] = useState<{
    totals: Record<string, number>
    items: Array<Record<string, string | null | undefined>>
  } | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState(false)
  const [pending, setPending] = useState<Record<string, PendingDraft>>({})
  const [metaTargetId, setMetaTargetId] = useState<string | null>(null)
  const [metaCode, setMetaCode] = useState('LATE')
  const [customNote, setCustomNote] = useState('')
  const [ownerId, setOwnerId] = useState('AHU_1')
  const [newEquipId, setNewEquipId] = useState('')
  const [newPointId, setNewPointId] = useState('')
  const [search, setSearch] = useState('')
  const [toast, setToast] = useState('')
  const [busy, setBusy] = useState(false)

  const allNodes = useMemo(() => flatten(tree), [tree])
  const metaTarget = allNodes.find((n) => n.id === metaTargetId) ?? null
  const pendingCount = Object.keys(pending).length

  const showToast = (text: string) => {
    setToast(text)
    window.setTimeout(() => setToast(''), 2400)
  }

  const loadTree = async () => {
    const body = await api<{
      revision: number
      allow_mutations: boolean
      tree: TreeNode[]
    }>('/api/model/tree')
    setTree(body.tree)
    setRevision(body.revision)
    setAllowMutations(body.allow_mutations)
    setExpanded((current) => (current.size > 0 ? current : branchIds(body.tree)))
  }

  useEffect(() => {
    Promise.all([loadTree(), api<Record<string, string>>('/api/model/meta-tags')])
      .then(([, tags]) => setMetaCatalog(tags))
      .catch((error) => showToast(error.message))
  }, [])

  useEffect(() => {
    if (tab !== 'dashboard') return
    api<{ totals: Record<string, number>; items: Array<Record<string, string | null>> }>(
      '/api/model/dashboard',
    )
      .then((body) => setDash(body))
      .catch((error) => showToast(error.message))
  }, [tab, revision])

  const patchPending = (id: string, patch: PendingDraft) => {
    setPending((current) => ({ ...current, [id]: { ...current[id], ...patch } }))
  }

  const savePending = async () => {
    const updates = Object.entries(pending).map(([point_id, draft]) => ({
      point_id,
      ...draft,
    }))
    if (!updates.length || busy) return
    setBusy(true)
    try {
      const body = await api<{ revision: number }>('/api/model/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates, expected_revision: revision }),
      })
      setPending({})
      setEditing(false)
      setMetaTargetId(null)
      setRevision(body.revision)
      showToast('Saved · writing building.ttl')
      await loadTree()
      await api('/api/model/ttl').catch(() => undefined)
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  const addEquipment = async () => {
    if (!newEquipId.trim()) return
    try {
      const body = await api<{ revision: number }>('/api/model/equip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          equipment_id: newEquipId.trim(),
          label: newEquipId.trim(),
          kind: 'ahu',
          parent_id: 'Building_50',
          expected_revision: revision,
        }),
      })
      setNewEquipId('')
      setRevision(body.revision)
      showToast('Equipment added')
      await loadTree()
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Add equip failed')
    }
  }

  const addPoint = async () => {
    if (!newPointId.trim() || !ownerId.trim()) return
    try {
      const body = await api<{ revision: number }>('/api/model/point', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          point_id: newPointId.trim(),
          owner_id: ownerId.trim(),
          label: newPointId.trim(),
          brick_class: 'Sensor',
          expected_revision: revision,
        }),
      })
      setNewPointId('')
      setRevision(body.revision)
      showToast('Point added (timeseries ref minted)')
      await loadTree()
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Add point failed')
    }
  }

  const hideSelectedOwner = async () => {
    if (!ownerId.trim()) return
    try {
      const body = await api<{ revision: number }>('/api/model/hide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_id: ownerId.trim(), expected_revision: revision }),
      })
      setRevision(body.revision)
      showToast('Hidden (timeseries refs kept)')
      await loadTree()
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Hide failed')
    }
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return tree
    const ids = new Set(
      allNodes
        .filter((n) => `${n.name} ${n.id} ${n.node_type}`.toLowerCase().includes(q))
        .map((n) => n.id),
    )
    const keep = (nodes: TreeNode[]): TreeNode[] =>
      nodes
        .map((n) => {
          const children = keep(n.children)
          if (ids.has(n.id) || children.length) return { ...n, children }
          return null
        })
        .filter((n): n is TreeNode => n !== null)
    return keep(tree)
  }, [tree, search, allNodes])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">B</div>
          <div className="brand-copy">
            <h1>Brick Model</h1>
            <p>
              Tag-tree tutorial · rev {revision}
              {allowMutations ? ' · mutations on' : ' · read-only (BRICKTS_ALLOW_MUTATIONS)'}
            </p>
          </div>
        </div>
        <div className="top-actions">
          <div className="tabs">
            <button className={`tab ${tab === 'floor' ? 'active' : ''}`} onClick={() => setTab('floor')}>
              Model
            </button>
            <button
              className={`tab ${tab === 'sparql' ? 'active' : ''}`}
              onClick={() => setTab('sparql')}
            >
              SPARQL
            </button>
            <button
              className={`tab ${tab === 'dashboard' ? 'active' : ''}`}
              onClick={() => setTab('dashboard')}
            >
              Dashboard
            </button>
          </div>
          <button
            className="ghost"
            onClick={() =>
              api('/api/model/flush', { method: 'POST' }).then(() => showToast('Wrote building.ttl'))
            }
          >
            Write TTL
          </button>
        </div>
      </header>

      {tab === 'sparql' ? (
        <SparqlPanel />
      ) : tab === 'floor' ? (
        <main className="workspace">
          <section className={`panel tree-panel ${editing ? 'is-editing' : ''}`}>
            <div className="panel-head">
              <div>
                <h2>Building tree</h2>
                <span>
                  {editing
                    ? 'Locked open · left Received · right Not received · hold Meta'
                    : 'Browse · Edit to tag points'}
                </span>
              </div>
              <div className="edit-controls">
                {!editing ? (
                  <button
                    className="primary-sm"
                    onClick={() => {
                      setExpanded(branchIds(tree))
                      setEditing(true)
                    }}
                  >
                    Edit
                  </button>
                ) : (
                  <>
                    <button
                      className="ghost"
                      onClick={() => {
                        setEditing(false)
                        setPending({})
                        setMetaTargetId(null)
                      }}
                    >
                      Discard
                    </button>
                    <button
                      className="primary-sm"
                      disabled={!pendingCount || busy}
                      onClick={savePending}
                    >
                      Save{pendingCount ? ` (${pendingCount})` : ''}
                    </button>
                  </>
                )}
              </div>
            </div>
            <div className="search">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search…"
              />
            </div>
            <div className="tree-scroll">
              {filtered.map((node) => (
                <DeepTree
                  key={node.iri}
                  node={node}
                  depth={0}
                  editing={editing}
                  lockedOpen={editing}
                  pending={pending}
                  metaTargetId={metaTargetId}
                  expanded={expanded}
                  onToggle={(id) =>
                    setExpanded((current) => {
                      const next = new Set(current)
                      if (next.has(id)) next.delete(id)
                      else next.add(id)
                      return next
                    })
                  }
                  onItemLeftClick={(item) => patchPending(item.id, { status: 'received' })}
                  onItemRightClick={(item) => patchPending(item.id, { status: 'not_received' })}
                  onItemHold={(item) => {
                    setMetaTargetId(item.id)
                    setMetaCode(pending[item.id]?.meta ?? item.tags.meta ?? 'LATE')
                    setCustomNote(pending[item.id]?.note ?? item.tags.custom ?? '')
                  }}
                  onSelectOwner={(item) => {
                    if (item.node_type !== 'point') setOwnerId(item.id)
                  }}
                />
              ))}
            </div>
          </section>

          <aside className="action-panel">
            <div className="selected-card">
              <div className="actions-label">Gestures (points)</div>
              <ul className="gesture-list">
                <li>
                  <b>Left</b> Received · <b>Right</b> Not received · <b>Hold</b> Meta
                </li>
                <li>
                  <b>Save</b> writes tags + refreshes <code>building.ttl</code>
                </li>
              </ul>

              {metaTarget && editing && (
                <div className="custom-panel">
                  <div className="actions-label">Meta · {metaTarget.name}</div>
                  <label className="field-label">
                    Tag
                    <select value={metaCode} onChange={(e) => setMetaCode(e.target.value)}>
                      {Object.entries(metaCatalog).map(([code, description]) => (
                        <option key={code} value={code}>
                          {code} — {description}
                        </option>
                      ))}
                    </select>
                  </label>
                  {metaCode === 'CUSTOM' && (
                    <div className="custom-box" style={{ marginTop: 8 }}>
                      <input
                        value={customNote}
                        onChange={(e) => setCustomNote(e.target.value)}
                        placeholder="Note…"
                      />
                    </div>
                  )}
                  <button
                    className="primary-sm"
                    style={{ marginTop: 10, width: '100%' }}
                    disabled={metaCode === 'CUSTOM' && !customNote.trim()}
                    onClick={() => {
                      patchPending(metaTarget.id, {
                        meta: metaCode,
                        note: metaCode === 'CUSTOM' ? customNote.trim() : undefined,
                      })
                      setMetaTargetId(null)
                      showToast(`${metaCode} staged`)
                    }}
                  >
                    Stage meta
                  </button>
                </div>
              )}

              <div className="actions-label" style={{ marginTop: 16 }}>
                Add / remove
              </div>
              <div className="custom-box" style={{ gridTemplateColumns: '1fr auto' }}>
                <input
                  value={newEquipId}
                  onChange={(e) => setNewEquipId(e.target.value)}
                  placeholder="New equipment id"
                />
                <button className="primary-sm" onClick={addEquipment} disabled={!allowMutations}>
                  Add equip
                </button>
              </div>
              <div className="custom-box" style={{ gridTemplateColumns: '1fr 1fr auto', marginTop: 8 }}>
                <input
                  value={ownerId}
                  onChange={(e) => setOwnerId(e.target.value)}
                  placeholder="Owner id"
                />
                <input
                  value={newPointId}
                  onChange={(e) => setNewPointId(e.target.value)}
                  placeholder="New point id"
                />
                <button className="primary-sm" onClick={addPoint} disabled={!allowMutations}>
                  Add point
                </button>
              </div>
              <button
                className="ghost"
                style={{ marginTop: 8 }}
                onClick={hideSelectedOwner}
                disabled={!allowMutations}
              >
                Hide `{ownerId}` (soft delete)
              </button>
              <p className="empty-hint" style={{ marginTop: 12 }}>
                Soft-delete hides nodes but keeps every TimeseriesReference.
              </p>
            </div>
          </aside>
        </main>
      ) : (
        <main className="dashboard">
          <div className="stat-grid">
            {['items', 'received', 'not_received', 'meta', 'untagged'].map((key) => (
              <div
                className={`stat ${
                  key === 'received'
                    ? 'received'
                    : key === 'not_received'
                      ? 'returned'
                      : key === 'meta'
                        ? 'custom'
                        : ''
                }`}
                key={key}
              >
                <div className="label">{key.replace('_', ' ')}</div>
                <div className="value">{dash?.totals?.[key] ?? '—'}</div>
              </div>
            ))}
          </div>
          <div className="card" style={{ marginTop: 12 }}>
            <div className="card-head">
              <h3>Points</h3>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Point</th>
                    <th>Status</th>
                    <th>Meta</th>
                    <th>Timeseries</th>
                  </tr>
                </thead>
                <tbody>
                  {(dash?.items ?? []).slice(0, 80).map((item) => (
                    <tr key={String(item.id)}>
                      <td>{item.name}</td>
                      <td>{statusPill(item.status as string | null)}</td>
                      <td>
                        {metaPill(item.meta as string | null, item.custom as string | null) ?? '—'}
                      </td>
                      <td>
                        <span className="mono">
                          {String(item.timeseries_id ?? '').slice(0, 13)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      )}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
