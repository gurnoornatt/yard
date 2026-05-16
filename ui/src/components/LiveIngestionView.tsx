import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// ─── Types ────────────────────────────────────────────────────────────────────

type NodeKind = 'root' | 'doc' | 'reasoning' | 'verdict'
type VerdictValue = 'PURSUE' | 'WATCHLIST' | 'PASS'

interface GraphNode {
  id: string
  kind: NodeKind
  label: string
  sub?: string       // doc: page ref / reasoning: metric detail
  verdict?: VerdictValue
  parentId: string | null
  col: number        // 0-based column in zig-zag layout
  row: number        // position within column
}

interface GraphEdge {
  id: string
  fromId: string
  toId: string
}

// ─── Beat script ─────────────────────────────────────────────────────────────
// Each beat adds one node (and its edge from parent).
// Thought narrates what just happened as that node appears.

interface Beat {
  node: Omit<GraphNode, 'col' | 'row'>  // layout computed automatically
  thought: string
}

const BEATS: Beat[] = [
  // col 0 — root (seeded before play, not a real beat; beat 0 is first child)
  // col 1 — doc nodes
  {
    node: { id: 'doc1', kind: 'doc', label: 'Executive Summary', sub: 'p. 3–4', parentId: 'root' },
    thought: 'Reading executive summary — extracting property overview and stated financials…',
  },
  {
    node: { id: 'doc2', kind: 'doc', label: 'Rent Roll', sub: 'p. 12', parentId: 'root' },
    thought: 'Pulling rent roll — cross-referencing unit count against stated occupancy…',
  },
  {
    node: { id: 'doc3', kind: 'doc', label: 'T-12 Financials', sub: 'p. 27', parentId: 'root' },
    thought: 'Examining trailing twelve-month financials — checking NOI against broker claims…',
  },
  {
    node: { id: 'doc4', kind: 'doc', label: 'Lease Abstracts', sub: 'p. 34', parentId: 'root' },
    thought: 'Scanning lease abstracts — noting concession burn-off schedule and expiry stack…',
  },
  {
    node: { id: 'doc5', kind: 'doc', label: 'Debt & Encumbrances', sub: 'p. 41', parentId: 'root' },
    thought: 'Reviewing debt schedule — checking lender, maturity date, and CMBS flag…',
  },
  // col 2 — reasoning off doc nodes
  {
    node: { id: 'r1', kind: 'reasoning', label: 'Vacancy 12% → above 8% submarket avg', parentId: 'doc2' },
    thought: 'Rent roll vacancy (12%) materially exceeds submarket average of 8% — flagging.',
  },
  {
    node: { id: 'r2', kind: 'reasoning', label: 'NOI reconciles within 1.2% of T-12', parentId: 'doc3' },
    thought: 'Stated NOI of $412k checks out against T-12 sum — broker figures are clean.',
  },
  {
    node: { id: 'r3', kind: 'reasoning', label: 'Concession burn-off risk in Q3', parentId: 'doc4' },
    thought: 'Three units on concession through August — effective rent will drop at expiry.',
  },
  {
    node: { id: 'r4', kind: 'reasoning', label: 'Frost Bank loan mature Mar 2026 — past due', parentId: 'doc5' },
    thought: 'Loan matured March 2026. Owner has not refinanced — classic forced-seller signal.',
  },
  {
    node: { id: 'r5', kind: 'reasoning', label: 'Owner held 11.3 yrs — out-of-state CT LLC', parentId: 'doc1' },
    thought: 'Long hold + out-of-state operator compound the motivation to exit quickly.',
  },
  // col 3 — secondary reasoning (convergence toward verdict)
  {
    node: { id: 'r6', kind: 'reasoning', label: 'Forced seller + motivated hold period', parentId: 'r4' },
    thought: 'Combining maturity signal with hold period — seller motivation is high.',
  },
  {
    node: { id: 'r7', kind: 'reasoning', label: 'Comps avg $156k/unit · ask $150k/unit', parentId: 'r2' },
    thought: 'Asking price $150k/unit sits 4% below submarket comps — pricing is attractive.',
  },
  {
    node: { id: 'r8', kind: 'reasoning', label: 'Vacancy correctible via capex — 1 permit filed', parentId: 'r1' },
    thought: 'Active permit on file for unit interiors — vacancy likely transitional, not structural.',
  },
  // verdict
  {
    node: { id: 'verdict', kind: 'verdict', label: 'PURSUE', verdict: 'PURSUE', parentId: 'r6' },
    thought: 'Motivated seller, below-market ask, correctible vacancy, clean financials. Recommend pursue.',
  },
]

// ─── Layout ──────────────────────────────────────────────────────────────────

function computeLayout(nodes: GraphNode[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()

  // Group by column
  const cols = new Map<number, GraphNode[]>()
  for (const n of nodes) {
    if (!cols.has(n.col)) cols.set(n.col, [])
    cols.get(n.col)!.push(n)
  }

  const COL_W = 220
  const ROW_H = 100

  for (const [col, colNodes] of cols) {
    const totalH = (colNodes.length - 1) * ROW_H
    colNodes.forEach((n, i) => {
      // Zig-zag: odd cols shift down by half a row
      const yOffset = col % 2 === 1 ? ROW_H / 2 : 0
      positions.set(n.id, {
        x: col * COL_W,
        y: -totalH / 2 + i * ROW_H + yOffset,
      })
    })
  }

  return positions
}

function assignLayout(nodes: GraphNode[]): GraphNode[] {
  // Build a col/row assignment by traversing from root
  const result: GraphNode[] = []
  const colCounters = new Map<number, number>()

  const place = (n: GraphNode, col: number) => {
    const row = colCounters.get(col) ?? 0
    colCounters.set(col, row + 1)
    result.push({ ...n, col, row })
  }

  const root = nodes.find(n => n.id === 'root')
  if (!root) return nodes

  // Assign columns by proximity to verdict (rough heuristic for a tree)
  const colMap = new Map<string, number>()

  const assignCol = (id: string, col: number) => {
    if (colMap.has(id)) return
    colMap.set(id, col)
    const children = nodes.filter(n => n.parentId === id)
    children.forEach(child => assignCol(child.id, col + 1))
  }
  assignCol('root', 0)

  // Sort so parent always before child
  const sorted = [...nodes].sort((a, b) => {
    const ca = colMap.get(a.id) ?? 0
    const cb = colMap.get(b.id) ?? 0
    return ca - cb
  })

  // Group by col and assign rows in order
  const placed = new Set<string>()
  sorted.forEach(n => {
    if (placed.has(n.id)) return
    place(n, colMap.get(n.id) ?? 0)
    placed.add(n.id)
  })

  return result
}

// ─── Node rendering ──────────────────────────────────────────────────────────

const VERDICT_COLOR: Record<VerdictValue, { bg: string; border: string; text: string; glow: string }> = {
  PURSUE:    { bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.5)',  text: '#10b981', glow: '0 0 30px rgba(16,185,129,0.25)' },
  WATCHLIST: { bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.5)', text: '#f59e0b', glow: '0 0 30px rgba(245,158,11,0.25)' },
  PASS:      { bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.5)',   text: '#ef4444', glow: '0 0 30px rgba(239,68,68,0.25)' },
}

function NodeBox({ node, isActive }: { node: GraphNode; isActive: boolean }) {
  if (node.kind === 'root') {
    return (
      <div style={{
        padding: '10px 16px', borderRadius: 10,
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.2)',
        boxShadow: isActive ? '0 0 20px rgba(99,102,241,0.35)' : 'none',
        minWidth: 160, textAlign: 'center',
      }}>
        <div style={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', color: '#8e9192', letterSpacing: '0.12em', marginBottom: 4 }}>DOCUMENT</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#e5e2e1' }}>{node.label}</div>
      </div>
    )
  }

  if (node.kind === 'verdict') {
    const vc = VERDICT_COLOR[node.verdict!]
    return (
      <div style={{
        padding: '12px 24px', borderRadius: 9999,
        background: vc.bg, border: `1.5px solid ${vc.border}`,
        boxShadow: vc.glow,
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: vc.text, letterSpacing: '0.15em', marginBottom: 2 }}>VERDICT</div>
        <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.01em', color: vc.text }}>{node.verdict}</div>
      </div>
    )
  }

  if (node.kind === 'doc') {
    return (
      <div style={{
        padding: '8px 14px', borderRadius: 8,
        background: 'rgba(99,102,241,0.08)',
        border: `1px solid ${isActive ? 'rgba(99,102,241,0.5)' : 'rgba(99,102,241,0.2)'}`,
        boxShadow: isActive ? '0 0 16px rgba(99,102,241,0.2)' : 'none',
        minWidth: 150,
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#a5b4fc' }}>{node.label}</div>
        {node.sub && <div style={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', color: 'rgba(165,180,252,0.5)', marginTop: 2 }}>{node.sub}</div>}
      </div>
    )
  }

  // reasoning
  return (
    <div style={{
      padding: '8px 14px', borderRadius: 8,
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${isActive ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.07)'}`,
      boxShadow: isActive ? '0 0 12px rgba(255,255,255,0.06)' : 'none',
      minWidth: 180, maxWidth: 210,
    }}>
      <div style={{ fontSize: 12, color: '#c4c7c8', lineHeight: 1.4 }}>{node.label}</div>
    </div>
  )
}

// ─── SVG edge ────────────────────────────────────────────────────────────────

function Edge({ from, to, active }: { from: { x: number; y: number }; to: { x: number; y: number }; active: boolean }) {
  const mx = (from.x + to.x) / 2
  const d = `M ${from.x} ${from.y} C ${mx} ${from.y}, ${mx} ${to.y}, ${to.x} ${to.y}`
  return (
    <motion.path
      d={d}
      fill="none"
      stroke={active ? 'rgba(99,102,241,0.6)' : 'rgba(255,255,255,0.1)'}
      strokeWidth={1.5}
      initial={{ pathLength: 0, opacity: 0 }}
      animate={{ pathLength: 1, opacity: 1 }}
      transition={{ duration: 0.45, ease: 'easeOut' }}
    />
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

const ROOT_NODE: GraphNode = {
  id: 'root', kind: 'root', label: 'Meridian_Plaza_OM.pdf',
  parentId: null, col: 0, row: 0,
}

export function LiveIngestionView({ onBack }: { onBack: () => void }) {
  const [visibleCount, setVisibleCount] = useState(0)   // how many beats revealed
  const [isPlaying, setIsPlaying]       = useState(false)
  const [thought, setThought]           = useState('Upload a document to begin the analysis.')
  const playTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const totalBeats = BEATS.length
  const isDone = visibleCount >= totalBeats

  // Build node + edge lists from revealed beats
  const revealedBeats = BEATS.slice(0, visibleCount)
  const rawNodes: GraphNode[] = [ROOT_NODE, ...revealedBeats.map(b => b.node as GraphNode)]
  const nodes = assignLayout(rawNodes)
  const edges: GraphEdge[] = revealedBeats
    .filter(b => b.node.parentId)
    .map(b => ({ id: `e-${b.node.id}`, fromId: b.node.parentId!, toId: b.node.id }))

  const positions = computeLayout(nodes)

  // Compute canvas bounds
  const allPos = [...positions.values()]
  const minX = Math.min(...allPos.map(p => p.x)) - 120
  const maxX = Math.max(...allPos.map(p => p.x)) + 220
  const minY = Math.min(...allPos.map(p => p.y)) - 80
  const maxY = Math.max(...allPos.map(p => p.y)) + 80
  const svgW = maxX - minX
  const svgH = maxY - minY

  const step = useCallback(() => {
    setVisibleCount(c => {
      const next = Math.min(c + 1, totalBeats)
      if (next > 0 && next <= totalBeats) {
        setThought(BEATS[next - 1].thought)
      }
      return next
    })
  }, [totalBeats])

  // Auto-play
  useEffect(() => {
    if (!isPlaying) { if (playTimer.current) clearTimeout(playTimer.current); return }
    if (isDone) { setIsPlaying(false); return }
    playTimer.current = setTimeout(() => step(), 1400)
    return () => { if (playTimer.current) clearTimeout(playTimer.current) }
  }, [isPlaying, isDone, visibleCount, step])

  const reset = () => {
    setIsPlaying(false)
    setVisibleCount(0)
    setThought('Upload a document to begin the analysis.')
  }

  const lastNode = visibleCount > 0 ? BEATS[visibleCount - 1].node.id : null

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: '#080808', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
      className="mesh-bg">

      {/* Header */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', height: 64, flexShrink: 0,
        background: 'rgba(8,8,8,0.7)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em', color: '#ffffff' }}>Sentinel</span>
          <span style={{ fontSize: 12, color: 'rgba(196,199,200,0.4)' }}>OM Analyzer</span>
          <span style={{ marginLeft: 8, fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: 'rgba(99,102,241,0.7)', letterSpacing: '0.1em' }}>LIVE</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(255,255,255,0.05)', padding: 4, borderRadius: 9999 }}>
          <button onClick={onBack} style={{ padding: '6px 16px', borderRadius: 9999, fontSize: 12, fontWeight: 500, background: 'transparent', color: '#c4c7c8', border: 'none', cursor: 'pointer' }}>History</button>
          <button style={{ padding: '6px 16px', borderRadius: 9999, fontSize: 12, fontWeight: 500, background: 'rgba(255,255,255,0.08)', color: '#ffffff', border: 'none', cursor: 'pointer' }}>Analyze</button>
        </div>
      </header>

      {/* Graph canvas — fills remaining height */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>

        {/* SVG edges */}
        {allPos.length > 0 && (
          <svg
            style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'visible' }}
            viewBox={`${minX} ${minY} ${svgW} ${svgH}`}
            width="100%" height="100%"
            preserveAspectRatio="xMidYMid meet"
          >
            <AnimatePresence>
              {edges.map(e => {
                const fp = positions.get(e.fromId)
                const tp = positions.get(e.toId)
                if (!fp || !tp) return null
                const isActive = e.toId === lastNode
                return <Edge key={e.id} from={fp} to={tp} active={isActive} />
              })}
            </AnimatePresence>
          </svg>
        )}

        {/* Node boxes */}
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ position: 'relative', width: svgW || 200, height: svgH || 200 }}>
            <AnimatePresence>
              {nodes.map(n => {
                const p = positions.get(n.id)
                if (!p) return null
                const isActive = n.id === lastNode
                return (
                  <motion.div
                    key={n.id}
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                    style={{
                      position: 'absolute',
                      left: p.x - minX,
                      top:  p.y - minY,
                      transform: 'translate(-50%, -50%)',
                      zIndex: isActive ? 10 : 1,
                    }}
                  >
                    <NodeBox node={n} isActive={isActive} />
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Bottom bar — thought + controls */}
      <div style={{
        flexShrink: 0, borderTop: '1px solid rgba(255,255,255,0.05)',
        background: 'rgba(8,8,8,0.85)', backdropFilter: 'blur(20px)',
        padding: '16px 32px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24,
      }}>
        {/* Streaming thought */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
          {(isPlaying || visibleCount > 0) && !isDone && (
            <motion.span
              animate={{ opacity: [1, 0, 1] }}
              transition={{ duration: 0.9, repeat: Infinity }}
              style={{ width: 6, height: 6, borderRadius: '50%', background: '#6366f1', flexShrink: 0 }}
            />
          )}
          {isDone && (
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
          )}
          <AnimatePresence mode="wait">
            <motion.p
              key={thought}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              style={{
                fontSize: 13, color: '#8e9192', fontStyle: 'italic',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}
            >
              {thought}
            </motion.p>
          </AnimatePresence>
        </div>

        {/* Progress */}
        <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: 'rgba(142,145,146,0.5)', flexShrink: 0 }}>
          {visibleCount}/{totalBeats}
        </span>

        {/* Controls */}
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          {isDone ? (
            <button onClick={reset} style={btnStyle('outline')}>Replay</button>
          ) : (
            <>
              <button
                onClick={step}
                disabled={isDone || isPlaying}
                style={btnStyle('outline', isDone || isPlaying)}
              >Step →</button>
              <button
                onClick={() => setIsPlaying(p => !p)}
                disabled={isDone}
                style={btnStyle('fill', isDone)}
              >{isPlaying ? 'Pause' : 'Play'}</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function btnStyle(variant: 'outline' | 'fill', disabled = false): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: '8px 18px', borderRadius: 7, fontSize: 12, fontWeight: 500,
    cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.35 : 1,
    transition: 'opacity 0.15s',
    fontFamily: 'inherit',
  }
  if (variant === 'fill') return { ...base, background: '#ffffff', color: '#141313', border: 'none' }
  return { ...base, background: 'transparent', color: '#c4c7c8', border: '1px solid rgba(255,255,255,0.12)' }
}
