import React, { useEffect, useMemo, useState } from 'react'
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

type Tab = 'floor' | 'dashboard' | 'sparql'

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

function pointIds(nodes: TreeNode[]): string[] {
  return flatten(nodes)
    .filter((n) => n.node_type === 'point')
    .map((n) => n.id)
}

function MarkerPills({ markers }: { markers: string[] }) {
  if (!markers.length) return <span className="pill none">untagged</span>
  return (
    <>
      {markers.map((m) => (
        <span key={m} className="pill custom">
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
  expanded: Set<string>
  checked: Set<string>
  busyId: string | null
  onToggle: (id: string) => void
  onCheck: (id: string, checked: boolean) => void
  onTagClick: (node: TreeNode) => void
}) {
  const { node, depth, editing, expanded } = props
  const isOpen = expanded.has(node.id)
  const hasChildren = node.children.length > 0
  const isPoint = node.node_type === 'point'
  const markers = node.markers ?? []

  return (
    <div className="tree-node">
      <div
        className={[
          'tree-row',
          isPoint ? 'item' : 'branch',
          editing && isPoint ? 'editable' : '',
          props.busyId === node.id ? 'staged-meta' : '',
          props.checked.has(node.id) ? 'custom-target' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        style={{ paddingLeft: `${10 + depth * 18}px` }}
        onClick={() => {
          if (editing && isPoint) {
            props.onTagClick(node)
            return
          }
          if (hasChildren) props.onToggle(node.id)
        }}
      >
        {editing && isPoint ? (
          <input
            type="checkbox"
            className="point-check"
            checked={props.checked.has(node.id)}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => props.onCheck(node.id, event.target.checked)}
            aria-label={`Select ${node.name}`}
          />
        ) : (
          <span
            className={`chevron ${hasChildren ? '' : 'placeholder'}`}
            style={{ transform: hasChildren && isOpen ? 'rotate(90deg)' : undefined }}
            onClick={(event) => {
              event.stopPropagation()
              if (hasChildren) props.onToggle(node.id)
            }}
          >
            {hasChildren ? '▸' : '·'}
          </span>
        )}
        <span className="node-copy">
          <span className="node-name">{node.name}</span>
          <span className="node-meta">
            <span className="pill none">{node.node_type}</span>
            <MarkerPills markers={markers} />
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
  } | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState(false)
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [busyId, setBusyId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [search, setSearch] = useState('')
  const [toast, setToast] = useState('')

  const allPoints = useMemo(() => pointIds(tree), [tree])

  const showToast = (text: string) => {
    setToast(text)
    window.setTimeout(() => setToast(''), 2600)
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
    }>('/api/model/dashboard')
      .then((body) => setDash(body))
      .catch((error) => showToast(error.message))
  }, [tab, revision])

  const guessAndSave = async (nodes: TreeNode[]) => {
    if (!nodes.length || busy) return
    if (!allowMutations) {
      showToast('Set BLDGTS_ALLOW_MUTATIONS=true')
      return
    }
    setBusy(true)
    try {
      const updates = []
      for (const node of nodes) {
        setBusyId(node.id)
        const bundle = await api<{ markers: string[] }>(
          `/api/model/haystack/guess?q=${encodeURIComponent(node.name)}&level=${encodeURIComponent(levelOf(node))}`,
        )
        updates.push({
          entity_id: node.id,
          markers: bundle.markers,
          level: levelOf(node),
        })
      }
      const body = await api<{ revision: number }>('/api/model/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates, expected_revision: revision }),
      })
      setRevision(body.revision)
      showToast(
        nodes.length === 1
          ? `Tagged ${nodes[0].id}: ${updates[0].markers.join(' ')}`
          : `Tagged ${nodes.length} points`,
      )
      setChecked(new Set())
      await loadTree()
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Tag failed')
    } finally {
      setBusy(false)
      setBusyId(null)
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

  const checkedNodes = useMemo(() => {
    const byId = new Map(flatten(tree).map((n) => [n.id, n]))
    return [...checked].map((id) => byId.get(id)).filter(Boolean) as TreeNode[]
  }, [checked, tree])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Project Haystack · FinStack-style tagging</p>
          <h1>Point tag tree</h1>
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
        <section className={`panel tree-panel tree-panel-full ${editing ? 'is-editing' : ''}`}>
          <div className="panel-head">
            <div>
              <h2>Building tree</h2>
              <p className="hint">
                {editing
                  ? 'Click a point → fuzzy guess all markers (point/sensor/sp/…) and CRUD to RDF. Checkboxes + “Tag selected” for batch.'
                  : 'Browse markers. Edit to one-shot tag like FinStack / Niagara.'}
              </p>
            </div>
            <div className="edit-controls">
              {!editing ? (
                <button type="button" disabled={!allowMutations} onClick={() => setEditing(true)}>
                  Edit
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => setChecked(new Set(allPoints))}
                    disabled={!allPoints.length}
                  >
                    Select all points
                  </button>
                  <button
                    type="button"
                    className="primary"
                    disabled={busy || !checkedNodes.length}
                    onClick={() => guessAndSave(checkedNodes)}
                  >
                    Tag selected ({checkedNodes.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false)
                      setChecked(new Set())
                    }}
                  >
                    Done
                  </button>
                </>
              )}
            </div>
          </div>
          <div className="search">
            <input
              placeholder="Filter by name or marker"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="tree-scroll">
            {filteredTree.map((node) => (
              <DeepTree
                key={node.id}
                node={node}
                depth={0}
                editing={editing}
                expanded={expanded}
                checked={checked}
                busyId={busyId}
                onToggle={(id) =>
                  setExpanded((current) => {
                    const next = new Set(current)
                    if (next.has(id)) next.delete(id)
                    else next.add(id)
                    return next
                  })
                }
                onCheck={(id, on) =>
                  setChecked((current) => {
                    const next = new Set(current)
                    if (on) next.add(id)
                    else next.delete(id)
                    return next
                  })
                }
                onTagClick={(node) => {
                  void guessAndSave([node])
                }}
              />
            ))}
          </div>
        </section>
      )}

      {toast ? <div className="toast">{toast}</div> : null}
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
