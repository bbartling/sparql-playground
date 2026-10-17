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
  hints?: string[]
  tagged?: boolean
  complete?: boolean
  coverage?: 'green' | 'yellow' | 'red'
  points_total?: number
  points_complete?: number
  tags: Record<string, string>
  children: TreeNode[]
}

type SuggestHit = { symbol: string; score?: number; doc?: string }

type Tab = 'floor' | 'rdf' | 'sparql'

type TagMenu = {
  node: TreeNode
  x: number
  y: number
  selected: string[]
  suggestions: string[]
}

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

function rollupCoverage(nodes: TreeNode[]): {
  status: 'green' | 'yellow' | 'red'
  total: number
  complete: number
} {
  const points = flatten(nodes).filter((n) => n.node_type === 'point')
  const total = points.length
  const complete = points.filter((n) => n.complete).length
  if (total === 0 || complete >= total) return { status: 'green', total, complete }
  if (complete === 0) return { status: 'red', total, complete }
  return { status: 'yellow', total, complete }
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

function StatusBar(props: {
  tone: 'green' | 'yellow' | 'red'
  title: string
  detail: string
}) {
  return (
    <div className={`status-bar status-${props.tone}`} role="status">
      <span className="status-dot" aria-hidden />
      <strong>{props.title}</strong>
      <span>{props.detail}</span>
    </div>
  )
}

function DeepTree(props: {
  node: TreeNode
  depth: number
  editing: boolean
  lockedOpen: boolean
  activeId: string | null
  expanded: Set<string>
  onToggle: (id: string) => void
  onPointClick: (node: TreeNode, event: React.MouseEvent) => void
}) {
  const { node, depth, lockedOpen, expanded } = props
  const isOpen = lockedOpen || expanded.has(node.id)
  const hasChildren = node.children.length > 0
  const isPoint = node.node_type === 'point'
  const markers = node.markers ?? []
  const coverage = node.coverage ?? (isPoint ? (node.complete ? 'green' : 'red') : undefined)

  return (
    <div>
      <button
        type="button"
        className={[
          'tree-row',
          isPoint ? 'item' : 'branch',
          props.editing && isPoint ? 'editable' : '',
          props.activeId === node.id ? 'custom-target' : '',
          coverage ? `coverage-${coverage}` : '',
        ]
          .filter(Boolean)
          .join(' ')}
        style={{ paddingLeft: `${10 + depth * 18}px` }}
        onClick={(event) => {
          if (props.editing && isPoint) {
            props.onPointClick(node, event)
            return
          }
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
            {!isPoint && node.points_total
              ? ` · ${node.points_complete ?? 0}/${node.points_total} tagged`
              : ''}
          </span>
        </span>
        {isPoint && (
          <span className="pill-stack">
            <MarkerPills markers={markers} />
          </span>
        )}
        {coverage ? <span className={`coverage-chip ${coverage}`} aria-label={coverage} /> : null}
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
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState(false)
  const [menu, setMenu] = useState<TagMenu | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [ttlText, setTtlText] = useState('')
  const [ttlBusy, setTtlBusy] = useState(false)
  const menuRef = useRef<HTMLDivElement | null>(null)

  const coverage = useMemo(() => rollupCoverage(tree), [tree])

  const showError = (text: string) => {
    setError(text)
    window.setTimeout(() => setError(''), 3200)
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

  const loadTtl = async () => {
    setTtlBusy(true)
    try {
      const response = await fetch('/api/model/ttl?scope=model')
      if (!response.ok) throw new Error(`TTL ${response.status}`)
      setTtlText(await response.text())
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to load Turtle')
      setTtlText('')
    } finally {
      setTtlBusy(false)
    }
  }

  useEffect(() => {
    loadTree().catch((err) => showError(err.message))
  }, [])

  useEffect(() => {
    if (tab !== 'rdf') return
    void loadTtl()
  }, [tab, revision])

  useEffect(() => {
    if (!menu) return
    const onDoc = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenu(null)
      }
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenu(null)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [menu])

  const openTagMenu = async (node: TreeNode, event: React.MouseEvent) => {
    if (!allowMutations || busy) return
    const x = Math.min(event.clientX, window.innerWidth - 280)
    const y = Math.min(event.clientY, window.innerHeight - 220)
    setMenu({
      node,
      x,
      y,
      selected: node.markers?.length ? node.markers : node.hints ?? [],
      suggestions: node.markers?.length ? node.markers : node.hints ?? [],
    })
    try {
      const [guess, suggest] = await Promise.all([
        api<{ markers: string[] }>(
          `/api/model/haystack/guess?q=${encodeURIComponent(node.name)}&level=${encodeURIComponent(levelOf(node))}`,
        ),
        api<{ suggestions: SuggestHit[] }>(
          `/api/model/haystack/suggest?q=${encodeURIComponent(node.name)}&level=${encodeURIComponent(levelOf(node))}&n=10`,
        ),
      ])
      const suggestions = [
        ...new Set([
          ...(guess.markers ?? []),
          ...(suggest.suggestions ?? []).map((h) => h.symbol),
        ]),
      ]
      setMenu((current) =>
        current && current.node.id === node.id
          ? {
              ...current,
              selected: guess.markers?.length ? guess.markers : current.selected,
              suggestions,
            }
          : current,
      )
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Suggest failed')
    }
  }

  const applyTags = async (markers: string[]) => {
    if (!menu || busy) return
    if (!allowMutations) {
      showError('Set BLDGTS_ALLOW_MUTATIONS=true')
      return
    }
    setBusy(true)
    try {
      const body = await api<{ revision: number }>('/api/model/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          updates: [
            {
              entity_id: menu.node.id,
              markers,
              level: levelOf(menu.node),
            },
          ],
          expected_revision: revision,
        }),
      })
      setRevision(body.revision)
      setMenu(null)
      await loadTree()
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Tag failed')
    } finally {
      setBusy(false)
    }
  }

  const toggleSelected = (symbol: string) => {
    setMenu((current) => {
      if (!current) return current
      const on = current.selected.includes(symbol)
      return {
        ...current,
        selected: on
          ? current.selected.filter((m) => m !== symbol)
          : [...current.selected, symbol],
      }
    })
  }

  const coverageTitle =
    coverage.status === 'green'
      ? 'Tagging complete'
      : coverage.status === 'yellow'
        ? 'Tagging in progress'
        : 'Points still need Haystack tags'

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">HS</div>
          <div className="brand-copy">
            <h1>Haystack point tagger</h1>
            <p>Edit · click a point · tag · done</p>
          </div>
        </div>
        <div className="top-actions">
          <span className="pill none">rev {revision}</span>
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
            ['rdf', 'RDF'],
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
        <SparqlPanel revision={revision} />
      ) : tab === 'rdf' ? (
        <main className="dashboard">
          <section className="panel" style={{ padding: 0, minHeight: 0, flex: 1 }}>
            <div className="panel-head">
              <div>
                <h2>Live RDF (Turtle)</h2>
                <span>GET /api/model/ttl</span>
              </div>
              <div className="edit-controls">
                <button type="button" className="ghost" onClick={() => void loadTtl()} disabled={ttlBusy}>
                  Refresh
                </button>
              </div>
            </div>
            <pre className="rdf-raw">{ttlBusy && !ttlText ? 'Loading…' : ttlText}</pre>
          </section>
        </main>
      ) : (
        <main className="workspace tree-only">
          <section className={`panel tree-panel tree-panel-full ${editing ? 'is-editing' : ''}`}>
            <StatusBar
              tone={coverage.status}
              title={coverageTitle}
              detail={`${coverage.complete}/${coverage.total} points complete (point+his+sensor|sp|cmd)`}
            />
            <div className="panel-head">
              <div>
                <h2>Building tree</h2>
                <span>{editing ? 'Locked · click a point to tag' : 'Scroll the tree · Edit to tag'}</span>
              </div>
              <div className="edit-controls">
                {!editing ? (
                  <button
                    type="button"
                    className="primary-sm"
                    disabled={!allowMutations}
                    onClick={() => {
                      setExpanded(branchIds(tree))
                      setEditing(true)
                    }}
                  >
                    Edit
                  </button>
                ) : (
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => {
                      setEditing(false)
                      setMenu(null)
                    }}
                  >
                    Done
                  </button>
                )}
              </div>
            </div>
            <div className="tree-scroll">
              {tree.map((node) => (
                <DeepTree
                  key={node.iri}
                  node={node}
                  depth={0}
                  editing={editing}
                  lockedOpen={editing}
                  activeId={menu?.node.id ?? null}
                  expanded={expanded}
                  onToggle={(id) =>
                    setExpanded((current) => {
                      const next = new Set(current)
                      if (next.has(id)) next.delete(id)
                      else next.add(id)
                      return next
                    })
                  }
                  onPointClick={(item, event) => {
                    void openTagMenu(item, event)
                  }}
                />
              ))}
            </div>
          </section>
        </main>
      )}

      {menu ? (
        <div
          ref={menuRef}
          className="tag-menu"
          style={{ left: menu.x, top: menu.y }}
          role="dialog"
          aria-label={`Tag ${menu.node.name}`}
        >
          <div className="tag-menu-head">{menu.node.name}</div>
          <div className="tag-menu-chips">
            {menu.suggestions.map((symbol) => (
              <button
                key={symbol}
                type="button"
                className={`preset-chip${menu.selected.includes(symbol) ? ' is-active' : ''}`}
                onClick={() => toggleSelected(symbol)}
              >
                {symbol}
              </button>
            ))}
          </div>
          <div className="tag-menu-actions">
            <button type="button" className="ghost tiny" onClick={() => setMenu(null)} disabled={busy}>
              Cancel
            </button>
            <button
              type="button"
              className="ghost tiny"
              onClick={() => void applyTags([])}
              disabled={busy}
            >
              Clear
            </button>
            <button
              type="button"
              className="primary-sm"
              onClick={() => void applyTags(menu.selected)}
              disabled={busy || !menu.selected.length}
            >
              Tag
            </button>
          </div>
        </div>
      ) : null}

      {error ? <div className="toast error">{error}</div> : null}
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
