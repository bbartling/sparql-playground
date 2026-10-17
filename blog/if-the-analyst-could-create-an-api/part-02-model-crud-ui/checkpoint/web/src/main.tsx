import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { SparqlPanel } from './SparqlPanel'
import './styles.css'

type TreeNode = {
  id: string
  iri: string
  name: string
  node_type: string
  markers?: string[]
  tags: Record<string, string>
  children: TreeNode[]
}

type PendingDraft = { markers: string[]; label?: string }

type Tab = 'floor' | 'dashboard' | 'sparql'
type Suggestion = { symbol: string; doc: string; score: number }

const HOLD_MS = 480

function levelOf(node: TreeNode): string {
  if (node.node_type === 'equipment') return 'equip'
  return node.node_type
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

function MarkerPills({ markers, pending }: { markers: string[]; pending?: boolean }) {
  if (!markers.length) return <span className="pill none">no markers</span>
  return (
    <>
      {markers.map((m) => (
        <span key={m} className={`pill ${pending ? 'pending custom' : 'custom'}`}>
          {m}
        </span>
      ))}
    </>
  )
}

function DeepTree(props: {
  node: TreeNode
  depth: number
  editing: boolean
  lockedOpen: boolean
  pending: Record<string, PendingDraft>
  activeId: string | null
  expanded: Set<string>
  onToggle: (id: string) => void
  onLeftClick: (node: TreeNode) => void
  onRightClick: (node: TreeNode) => void
  onHold: (node: TreeNode) => void
  onSelectOwner: (node: TreeNode) => void
}) {
  const { node, depth, lockedOpen, expanded, editing } = props
  const isOpen = lockedOpen || expanded.has(node.id)
  const hasChildren = node.children.length > 0
  const staged = props.pending[node.id]
  const markers = staged?.markers ?? node.markers ?? []
  const name = staged?.label ?? node.name
  const holdTimer = useRef<number | null>(null)
  const holdFired = useRef(false)
  const clearHold = () => {
    if (holdTimer.current != null) window.clearTimeout(holdTimer.current)
    holdTimer.current = null
  }

  return (
    <div className="tree-node">
      <div
        className={[
          'tree-row',
          node.node_type === 'point' ? 'item' : 'branch',
          staged ? 'staged-meta' : '',
          props.activeId === node.id ? 'custom-target' : '',
          editing ? 'editable' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        style={{ paddingLeft: `${10 + depth * 18}px` }}
        onContextMenu={(event) => {
          if (!editing) return
          event.preventDefault()
          props.onRightClick(node)
        }}
        onPointerDown={(event) => {
          if (!editing || event.button !== 0) return
          holdFired.current = false
          clearHold()
          holdTimer.current = window.setTimeout(() => {
            holdFired.current = true
            props.onHold(node)
          }, HOLD_MS)
        }}
        onPointerUp={clearHold}
        onPointerLeave={clearHold}
        onPointerCancel={clearHold}
        onClick={() => {
          if (editing) {
            if (holdFired.current) {
              holdFired.current = false
              return
            }
            props.onLeftClick(node)
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
          <span className="node-name">
            {name}
            {staged ? ' · pending' : ''}
          </span>
          <span className="node-meta">
            <span className="pill none">{node.node_type}</span>
            <MarkerPills markers={markers} pending={Boolean(staged)} />
          </span>
        </span>
      </div>
      {hasChildren && isOpen
        ? node.children.map((child) => (
            <DeepTree key={child.id} {...props} node={child} depth={depth + 1} />
          ))
        : null}
    </div>
  )
}

function App() {
  const [tab, setTab] = useState<Tab>('floor')
  const [tree, setTree] = useState<TreeNode[]>([])
  const [revision, setRevision] = useState(0)
  const [allowMutations, setAllowMutations] = useState(false)
  const [dash, setDash] = useState<{
    totals: Record<string, number>
    marker_counts: Record<string, number>
    items: Array<{ id: string; name: string; markers: string[] }>
  } | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState(false)
  const [pending, setPending] = useState<Record<string, PendingDraft>>({})
  const [activeId, setActiveId] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [catalog, setCatalog] = useState<Record<string, string>>({})
  const [manualMarker, setManualMarker] = useState('')
  const [renameValue, setRenameValue] = useState('')
  const [ownerId, setOwnerId] = useState('AHU_1')
  const [newEquipId, setNewEquipId] = useState('')
  const [newPointId, setNewPointId] = useState('')
  const [search, setSearch] = useState('')
  const [toast, setToast] = useState('')
  const [busy, setBusy] = useState(false)

  const allNodes = useMemo(() => flatten(tree), [tree])
  const active = allNodes.find((n) => n.id === activeId) ?? null
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
    loadTree().catch((error) => showToast(error.message))
  }, [])

  useEffect(() => {
    if (tab !== 'dashboard') return
    api<{
      totals: Record<string, number>
      marker_counts: Record<string, number>
      items: Array<{ id: string; name: string; markers: string[] }>
    }>('/api/model/dashboard')
      .then((body) => setDash(body))
      .catch((error) => showToast(error.message))
  }, [tab, revision])

  const openSuggest = async (node: TreeNode) => {
    setActiveId(node.id)
    setRenameValue(pending[node.id]?.label ?? node.name)
    const level = levelOf(node)
    const [sug, cat] = await Promise.all([
      api<{ suggestions: Suggestion[] }>(
        `/api/model/haystack/suggest?q=${encodeURIComponent(node.name)}&level=${encodeURIComponent(level)}`,
      ),
      api<{ catalog: Record<string, string> }>(
        `/api/model/haystack/catalog?level=${encodeURIComponent(level)}`,
      ),
    ])
    setSuggestions(sug.suggestions)
    setCatalog(cat.catalog)
  }

  const stageMarkers = (node: TreeNode, markers: string[]) => {
    const unique = [...new Set(markers.filter(Boolean))]
    setPending((current) => ({
      ...current,
      [node.id]: {
        markers: unique,
        label: current[node.id]?.label,
      },
    }))
  }

  const savePending = async () => {
    const markerUpdates = Object.entries(pending)
      .filter(([, draft]) => draft.markers?.length)
      .map(([entity_id, draft]) => {
        const node = allNodes.find((n) => n.id === entity_id)
        return {
          entity_id,
          markers: draft.markers,
          level: node ? levelOf(node) : 'point',
        }
      })
    const renames = Object.entries(pending).filter(([, draft]) => draft.label)
    if ((!markerUpdates.length && !renames.length) || busy) return
    setBusy(true)
    try {
      if (markerUpdates.length) {
        const body = await api<{ revision: number }>('/api/model/tags', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ updates: markerUpdates, expected_revision: revision }),
        })
        setRevision(body.revision)
      }
      for (const [entity_id, draft] of renames) {
        if (!draft.label) continue
        const body = await api<{ revision: number }>('/api/model/rename', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            entity_id,
            label: draft.label,
            expected_revision: revision,
          }),
        })
        setRevision(body.revision)
      }
      setPending({})
      setEditing(false)
      setActiveId(null)
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
      showToast('Point added')
      await loadTree()
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Add point failed')
    }
  }

  const hideActive = async () => {
    if (!active) return
    try {
      const body = await api<{ revision: number }>('/api/model/hide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_id: active.id, expected_revision: revision }),
      })
      setRevision(body.revision)
      setActiveId(null)
      showToast('Hidden')
      await loadTree()
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Hide failed')
    }
  }

  const filteredTree = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return tree
    const match = (node: TreeNode): TreeNode | null => {
      const self =
        node.name.toLowerCase().includes(q) ||
        node.id.toLowerCase().includes(q) ||
        (node.markers ?? []).some((m) => m.toLowerCase().includes(q))
      const kids = node.children.map(match).filter(Boolean) as TreeNode[]
      if (self || kids.length) return { ...node, children: kids }
      return null
    }
    return tree.map(match).filter(Boolean) as TreeNode[]
  }, [tree, search])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Project Haystack · smart building IoT</p>
          <h1>Model tag tree</h1>
        </div>
        <div className="topbar-meta">
          <span>rev {revision}</span>
          <span className={allowMutations ? 'pill received' : 'pill none'}>
            {allowMutations ? 'mutations on' : 'read-only'}
          </span>
        </div>
      </header>

      <nav className="tabs">
        {(
          [
            ['floor', 'Model'],
            ['sparql', 'SPARQL'],
            ['dashboard', 'Coverage'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            className={tab === id ? 'tab active' : 'tab'}
            onClick={() => setTab(id)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === 'sparql' ? (
        <SparqlPanel showToast={showToast} />
      ) : tab === 'dashboard' ? (
        <section className="panel">
          <h2>Haystack marker coverage</h2>
          <div className="dash-grid">
            {['items', 'tagged', 'untagged', 'distinct_markers'].map((key) => (
              <div key={key} className="dash-card">
                <div className="dash-label">{key}</div>
                <div className="dash-value">{dash?.totals?.[key] ?? '—'}</div>
              </div>
            ))}
          </div>
          <h3>Top markers</h3>
          <ul className="dash-list">
            {Object.entries(dash?.marker_counts ?? {})
              .slice(0, 24)
              .map(([marker, count]) => (
                <li key={marker}>
                  <code>{marker}</code> · {count}
                </li>
              ))}
          </ul>
        </section>
      ) : (
        <div className="floor-layout">
          <section className={`panel tree-panel ${editing ? 'is-editing' : ''}`}>
            <div className="panel-head">
              <div>
                <h2>Building tree</h2>
                <p className="hint">
                  {editing
                    ? 'Hold = rename · Right-click = closest Haystack markers · Save writes TTL'
                    : 'Browse · Edit to tag with Haystack markers'}
                </p>
              </div>
              <div className="edit-controls">
                {!editing ? (
                  <button type="button" disabled={!allowMutations} onClick={() => setEditing(true)}>
                    Edit
                  </button>
                ) : (
                  <>
                    <button type="button" className="primary" disabled={busy || !pendingCount} onClick={savePending}>
                      Save{pendingCount ? ` (${pendingCount})` : ''}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(false)
                        setPending({})
                        setActiveId(null)
                      }}
                    >
                      Cancel
                    </button>
                  </>
                )}
              </div>
            </div>
            <input
              className="search"
              placeholder="Filter by name or marker"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div className="tree-scroll">
              {filteredTree.map((node) => (
                <DeepTree
                  key={node.id}
                  node={node}
                  depth={0}
                  editing={editing}
                  lockedOpen={editing}
                  pending={pending}
                  activeId={activeId}
                  expanded={expanded}
                  onToggle={(id) =>
                    setExpanded((current) => {
                      const next = new Set(current)
                      if (next.has(id)) next.delete(id)
                      else next.add(id)
                      return next
                    })
                  }
                  onLeftClick={(node) => {
                    setActiveId(node.id)
                    setRenameValue(pending[node.id]?.label ?? node.name)
                  }}
                  onRightClick={(node) => {
                    openSuggest(node).catch((error) => showToast(error.message))
                  }}
                  onHold={(node) => {
                    setActiveId(node.id)
                    setRenameValue(pending[node.id]?.label ?? node.name)
                    showToast('Rename — edit label below')
                  }}
                  onSelectOwner={(node) => {
                    if (node.node_type === 'equipment' || node.node_type === 'part') {
                      setOwnerId(node.id)
                    }
                  }}
                />
              ))}
            </div>
          </section>

          <aside className="panel side-panel">
            <h2>Haystack tags</h2>
            {!allowMutations && (
              <p className="hint">Set <code>BRICKTS_ALLOW_MUTATIONS=true</code> to edit.</p>
            )}
            {active && editing ? (
              <>
                <p className="hint">
                  Selected <b>{active.id}</b> · level <code>{levelOf(active)}</code>
                </p>
                <label className="field">
                  Display name
                  <input
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => {
                      if (renameValue.trim() && renameValue.trim() !== active.name) {
                        setPending((current) => ({
                          ...current,
                          [active.id]: {
                            markers: current[active.id]?.markers ?? active.markers ?? [],
                            label: renameValue.trim(),
                          },
                        }))
                      }
                    }}
                  />
                </label>
                <div className="tag-row">
                  <MarkerPills markers={pending[active.id]?.markers ?? active.markers ?? []} pending />
                </div>
                <h3>Closest matches</h3>
                <ul className="dash-list">
                  {suggestions.map((s) => (
                    <li key={s.symbol}>
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => {
                          const base = pending[active.id]?.markers ?? active.markers ?? []
                          stageMarkers(active, [...base, s.symbol])
                          showToast(`staged ${s.symbol}`)
                        }}
                      >
                        <code>{s.symbol}</code>
                      </button>
                      <span className="hint"> {s.doc.slice(0, 72)}</span>
                    </li>
                  ))}
                </ul>
                <label className="field">
                  Add marker
                  <select value={manualMarker} onChange={(e) => setManualMarker(e.target.value)}>
                    <option value="">Select…</option>
                    {Object.keys(catalog).map((sym) => (
                      <option key={sym} value={sym}>
                        {sym}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  disabled={!manualMarker}
                  onClick={() => {
                    const base = pending[active.id]?.markers ?? active.markers ?? []
                    stageMarkers(active, [...base, manualMarker])
                    setManualMarker('')
                  }}
                >
                  Stage marker
                </button>
                <button type="button" onClick={hideActive}>
                  Soft-delete
                </button>
              </>
            ) : (
              <p className="hint">Enter Edit, then right-click a node for marker suggestions.</p>
            )}

            <h3>Add equipment / point</h3>
            <label className="field">
              New equip id
              <input value={newEquipId} onChange={(e) => setNewEquipId(e.target.value)} disabled={!allowMutations} />
            </label>
            <button type="button" disabled={!allowMutations} onClick={addEquipment}>
              Add AHU equip
            </button>
            <label className="field">
              Owner
              <input value={ownerId} onChange={(e) => setOwnerId(e.target.value)} disabled={!allowMutations} />
            </label>
            <label className="field">
              New point id
              <input value={newPointId} onChange={(e) => setNewPointId(e.target.value)} disabled={!allowMutations} />
            </label>
            <button type="button" disabled={!allowMutations} onClick={addPoint}>
              Add sensor point
            </button>
          </aside>
        </div>
      )}

      {toast ? <div className="toast">{toast}</div> : null}
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
