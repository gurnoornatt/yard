import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload } from 'lucide-react'
import type { AnalysisState } from '../types'
import { SKILL_ORDER } from '../App'

// ── Virtual canvas dimensions ─────────────────────────────────────────────────
// Root and verdict are centered vertically; doc/reasoning nodes fill rows 0-9.

const X_ROOT    = 100
const X_DOC     = 370
const X_REASON  = 650
const X_VERDICT = 930
const Y_TOP     = 40
const ROW_H     = 56
const CANVAS_W  = 1080
const CANVAS_H  = 630   // Y_TOP + 9*ROW_H + 86 headroom

// ── Node types ────────────────────────────────────────────────────────────────

type NodeKind   = 'root' | 'doc' | 'reasoning' | 'verdict'
type VerdictVal = 'PURSUE' | 'WATCHLIST' | 'PASS'

interface GNode {
  id: string
  kind: NodeKind
  label: string
  sub?: string
  verdict?: VerdictVal
  row: number   // 0-9, skill index (ignored for root/verdict)
}

// ── Skill metadata ────────────────────────────────────────────────────────────

const SKILL_META: Record<string, { label: string; sub: string }> = {
  parse_om:            { label: 'Offering Memorandum', sub: 'full document'       },
  owner_lookup:        { label: 'Owner Records',       sub: 'county records'      },
  deed_lookup:         { label: 'Deed & Loans',        sub: 'county clerk'        },
  portfolio_crawler:   { label: 'Owner Portfolio',     sub: 'cross-reference'     },
  permit_lookup:       { label: 'Building Permits',    sub: 'city records'        },
  tax_lookup:          { label: 'Tax Status',          sub: 'appraisal district'  },
  violations_lookup:   { label: 'Code Violations',     sub: 'city enforcement'    },
  comps_lookup:        { label: 'Market Comps',        sub: 'submarket data'      },
  maturity_estimator:  { label: 'Loan Maturity',       sub: 'calculated'          },
  synthesize_analysis: { label: 'Research Brief',      sub: 'all sources'         },
}

// ── Extract a one-line finding from completed skill data ──────────────────────

function finding(skill: string, data: Record<string, unknown>): string | null {
  switch (skill) {
    case 'parse_om': {
      const u = data.units as number | undefined
      const y = data.year_built as number | undefined
      const p = data.asking_price as number | undefined
      return [u && u + ' units', y, p && '$' + (p / 1e6).toFixed(1) + 'M ask'].filter(Boolean).join(' · ') || null
    }
    case 'owner_lookup': {
      const name = String(data.owner_name ?? '—')
      const oos  = data.out_of_state as boolean | undefined
      return [name, oos && 'out-of-state (' + data.owner_state + ')'].filter(Boolean).join(' · ')
    }
    case 'deed_lookup': {
      const lender = data.lender ? String(data.lender) : null
      const amt    = data.loan_amount ? '$' + (Number(data.loan_amount) / 1e6).toFixed(1) + 'M loan' : null
      const mat    = data.maturity_date ? 'matures ' + String(data.maturity_date) : null
      return [lender, amt, mat].filter(Boolean).join(' · ') || 'No deed data'
    }
    case 'tax_lookup':
      return data.delinquent
        ? 'Delinquent · ' + String(data.total_due ?? 'amount unknown') + ' owed'
        : 'Taxes current'
    case 'violations_lookup': {
      const n = (data.open_count as number) ?? 0
      return n > 0 ? n + ' open violation' + (n > 1 ? 's' : '') : 'No open violations'
    }
    case 'comps_lookup': {
      const market = data.market as Record<string, unknown> | undefined
      const rent   = market?.median_rent ? '$' + Number(market.median_rent).toLocaleString() + '/mo median rent' : null
      const vac    = market?.vacancy_pct != null ? market.vacancy_pct + '% vacancy' : null
      return [rent, vac].filter(Boolean).join(' · ') || null
    }
    case 'permit_lookup': {
      const n = (data.count as number) ?? (data.permits as Array<unknown> | undefined)?.length ?? 0
      return n + ' permit' + (n !== 1 ? 's' : '') + ' on file'
    }
    case 'portfolio_crawler': {
      const n = (data.property_count as number) ?? (data.properties as Array<unknown> | undefined)?.length ?? 0
      return n + ' propert' + (n !== 1 ? 'ies' : 'y') + ' in portfolio'
    }
    case 'maturity_estimator': {
      const m = data.months_remaining as number | undefined
      if (m === undefined) return null
      return m < 0
        ? Math.abs(m) + ' months past due — high refi pressure'
        : m + ' months to maturity · ' + String(data.pressure_level ?? '')
    }
    case 'synthesize_analysis':
      return 'Compiling analysis brief…'
    default:
      return null
  }
}

// ── Build node list from live state ──────────────────────────────────────────

function buildNodes(state: AnalysisState, fileName: string): GNode[] {
  const nodes: GNode[] = [{ id: 'root', kind: 'root', label: fileName, row: 0 }]

  SKILL_ORDER.forEach((sk, i) => {
    const s = state.skills[sk]
    if (!s || s.status === 'idle') return
    nodes.push({ id: 'doc-' + sk, kind: 'doc', label: SKILL_META[sk].label, sub: SKILL_META[sk].sub, row: i })
    if ((s.status === 'complete' || s.status === 'error') && s.data) {
      const f = finding(sk, s.data)
      if (f) nodes.push({ id: 'r-' + sk, kind: 'reasoning', label: f, row: i })
    }
  })

  if (state.verdict) {
    nodes.push({ id: 'verdict', kind: 'verdict', label: state.verdict, verdict: state.verdict as VerdictVal, row: 0 })
  }

  return nodes
}

// ── Node → canvas position ────────────────────────────────────────────────────

function pos(n: GNode): { x: number; y: number } {
  if (n.kind === 'root')      return { x: X_ROOT,    y: CANVAS_H / 2 }
  if (n.kind === 'verdict')   return { x: X_VERDICT, y: CANVAS_H / 2 }
  if (n.kind === 'doc')       return { x: X_DOC,     y: Y_TOP + n.row * ROW_H }
  /* reasoning */              return { x: X_REASON,  y: Y_TOP + n.row * ROW_H }
}

// ── Derive "active" node id ───────────────────────────────────────────────────

function activeId(state: AnalysisState, nodes: GNode[]): string {
  if (state.verdict) return 'verdict'
  for (let i = SKILL_ORDER.length - 1; i >= 0; i--) {
    const sk = state.skills[SKILL_ORDER[i]]
    if (!sk) continue
    if (sk.status === 'complete' && nodes.find(n => n.id === 'r-' + SKILL_ORDER[i])) return 'r-' + SKILL_ORDER[i]
    if (sk.status === 'running') return 'doc-' + SKILL_ORDER[i]
  }
  return 'root'
}

// ── Bottom thought line ───────────────────────────────────────────────────────

function thought(state: AnalysisState): string {
  if (state.verdict) return 'Analysis complete — verdict: ' + state.verdict
  if (state.synthesisText) {
    const lines = state.synthesisText.split('\n').filter(l => l.trim() && !l.startsWith('##'))
    const last  = lines[lines.length - 1] ?? ''
    return last.slice(0, 110) + (last.length > 110 ? '…' : '') || 'Writing analysis…'
  }
  const running = [...SKILL_ORDER].reverse().find(n => state.skills[n]?.status === 'running')
  if (running) return 'Checking ' + SKILL_META[running].label.toLowerCase() + '…'
  const done = [...SKILL_ORDER].reverse().find(n => state.skills[n]?.status === 'complete')
  if (done) return SKILL_META[done].label + ' complete.'
  if (state.phase === 'uploading') return 'Uploading document…'
  return 'Initializing…'
}

// ── Extract reasoning from synthesis text ─────────────────────────────────────

function extractReasoning(text: string): string {
  const idx = text.indexOf('## Bottom-Line Recommendation')
  if (idx === -1) return ''
  const after = text.slice(idx + '## Bottom-Line Recommendation'.length).trimStart()
  const next  = after.indexOf('\n## ')
  const block = next !== -1 ? after.slice(0, next) : after
  return block.replace(/^(PURSUE|WATCHLIST|PASS)\s*/i, '').trim()
}

// ── Verdict color config ──────────────────────────────────────────────────────

const VC: Record<VerdictVal, { bg: string; border: string; text: string; glow: string }> = {
  PURSUE:    { bg: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.5)',  text: '#10b981', glow: '0 0 28px rgba(16,185,129,0.25)' },
  WATCHLIST: { bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.5)', text: '#f59e0b', glow: '0 0 28px rgba(245,158,11,0.25)' },
  PASS:      { bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.5)',   text: '#ef4444', glow: '0 0 28px rgba(239,68,68,0.25)'  },
}

// ── Node box ──────────────────────────────────────────────────────────────────

function NodeBox({ n, active }: { n: GNode; active: boolean }) {
  if (n.kind === 'root') return (
    <div style={{
      padding: '8px 16px', borderRadius: 10, minWidth: 150, maxWidth: 180, textAlign: 'center',
      background: 'rgba(255,255,255,0.05)',
      border: '1px solid ' + (active ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.14)'),
      boxShadow: active ? '0 0 18px rgba(99,102,241,0.3)' : 'none',
    }}>
      <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono,monospace', color: '#8e9192', letterSpacing: '0.1em', marginBottom: 3 }}>DOCUMENT</div>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#e5e2e1', wordBreak: 'break-all', lineHeight: 1.3 }}>{n.label}</div>
    </div>
  )

  if (n.kind === 'verdict') {
    const v = VC[n.verdict!]
    return (
      <div style={{
        padding: '10px 22px', borderRadius: 9999, textAlign: 'center',
        background: v.bg, border: '1.5px solid ' + v.border, boxShadow: v.glow,
      }}>
        <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono,monospace', color: v.text, letterSpacing: '0.12em', marginBottom: 3 }}>VERDICT</div>
        <div style={{ fontSize: 17, fontWeight: 700, color: v.text }}>{n.verdict}</div>
      </div>
    )
  }

  if (n.kind === 'doc') return (
    <div style={{
      padding: '5px 11px', borderRadius: 7, minWidth: 130,
      background: active ? 'rgba(99,102,241,0.13)' : 'rgba(99,102,241,0.06)',
      border: '1px solid ' + (active ? 'rgba(99,102,241,0.55)' : 'rgba(99,102,241,0.2)'),
      boxShadow: active ? '0 0 12px rgba(99,102,241,0.2)' : 'none',
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: active ? '#a5b4fc' : '#818cf8' }}>{n.label}</div>
      {n.sub && <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono,monospace', color: 'rgba(129,140,248,0.45)', marginTop: 1 }}>{n.sub}</div>}
    </div>
  )

  // reasoning
  return (
    <div style={{
      padding: '5px 11px', borderRadius: 7, maxWidth: 205,
      background: active ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.02)',
      border: '1px solid ' + (active ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.07)'),
    }}>
      <div style={{ fontSize: 11, color: '#c4c7c8', lineHeight: 1.4 }}>{n.label}</div>
    </div>
  )
}

// ── SVG edge ──────────────────────────────────────────────────────────────────

function Edge({ from, to, lit }: { from: { x: number; y: number }; to: { x: number; y: number }; lit: boolean }) {
  const mx = (from.x + to.x) / 2
  const d  = `M ${from.x} ${from.y} C ${mx} ${from.y}, ${mx} ${to.y}, ${to.x} ${to.y}`
  return (
    <motion.path d={d} fill="none"
      stroke={lit ? 'rgba(99,102,241,0.75)' : 'rgba(255,255,255,0.08)'}
      strokeWidth={lit ? 1.5 : 1}
      initial={{ pathLength: 0, opacity: 0 }}
      animate={{ pathLength: 1, opacity: 1 }}
      transition={{ duration: 0.38, ease: 'easeOut' }}
    />
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export function IngestionView({ state, file, onFile, onBack }: {
  state:  AnalysisState
  file:   File | null
  onFile: (f: File) => void
  onBack: () => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [scale,    setScale]    = useState(1)
  const [dragging, setDragging] = useState(false)

  const isRunning = state.phase === 'uploading' || state.phase === 'analyzing'
  const isDone    = state.phase === 'done'
  const nodes     = file ? buildNodes(state, file.name) : []
  const posMap    = new Map(nodes.map(n => [n.id, pos(n)]))
  const active    = file ? activeId(state, nodes) : ''
  const currentThought = file ? thought(state) : 'Drop a PDF to begin the analysis.'
  const doneCount = Object.values(state.skills).filter(s => s.status === 'complete').length

  // Build edges
  const edges = nodes.flatMap(n => {
    let pId: string | null = null
    if (n.kind === 'doc')       pId = 'root'
    else if (n.kind === 'reasoning') pId = 'doc-' + n.id.replace('r-', '')
    else if (n.kind === 'verdict') {
      const rSynth = nodes.find(x => x.id === 'r-synthesize_analysis')
      const lastR  = [...nodes].reverse().find(x => x.kind === 'reasoning')
      pId = rSynth?.id ?? lastR?.id ?? 'root'
    }
    if (!pId) return []
    const from = posMap.get(pId); const to = posMap.get(n.id)
    if (!from || !to) return []
    const lit = n.id === active || pId === active
    return [{ id: 'e-' + n.id, from, to, lit }]
  })

  // Scale graph to fit container
  useEffect(() => {
    const el = containerRef.current
    if (!el || !file) return
    const s = Math.min((el.offsetWidth - 40) / CANVAS_W, (el.offsetHeight - 40) / CANVAS_H, 1)
    setScale(s)
  }, [file, nodes.length])

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]; if (f) onFile(f)
  }
  const openPicker = () => {
    if (file) return
    const inp = document.createElement('input')
    inp.type = 'file'; inp.accept = '.pdf'
    inp.onchange = ev => { const f = (ev.target as HTMLInputElement).files?.[0]; if (f) onFile(f) }
    inp.click()
  }

  return (
    <div className="mesh-bg" style={{ minHeight: '100vh', background: '#080808', display: 'flex', flexDirection: 'column' }}>

      {/* ── Header ── */}
      <header style={{
        flexShrink: 0, position: 'sticky', top: 0, zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', height: 64,
        background: 'rgba(8,8,8,0.75)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em', color: '#fff' }}>Sentinel</span>
          <span style={{ fontSize: 12, color: 'rgba(196,199,200,0.4)' }}>OM Analyzer</span>
          {isRunning && (
            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.4, repeat: Infinity }}
              style={{ marginLeft: 8, fontSize: 10, fontFamily: 'JetBrains Mono,monospace', color: 'rgba(99,102,241,0.85)', letterSpacing: '0.12em' }}>
              LIVE
            </motion.span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 4, background: 'rgba(255,255,255,0.05)', padding: 4, borderRadius: 9999 }}>
          <button onClick={onBack} style={{ padding: '6px 16px', borderRadius: 9999, fontSize: 12, fontWeight: 500, background: 'transparent', color: '#c4c7c8', border: 'none', cursor: 'pointer' }}>History</button>
          <button style={{ padding: '6px 16px', borderRadius: 9999, fontSize: 12, fontWeight: 500, background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', cursor: 'pointer' }}>Analyze</button>
        </div>
      </header>

      {/* ── Graph / upload area ── */}
      <div ref={containerRef} style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>

        {/* Upload zone */}
        <AnimatePresence>
          {!file && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97 }}
              className="glass"
              onClick={openPicker}
              onDrop={handleDrop}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              style={{
                width: 400, padding: '52px 40px', borderRadius: 16, cursor: 'pointer',
                border: `2px dashed ${dragging ? 'rgba(99,102,241,0.6)' : 'rgba(255,255,255,0.1)'}`,
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20,
                transition: 'border-color 0.2s',
              }}
            >
              <div style={{ padding: 16, background: 'rgba(255,255,255,0.04)', borderRadius: '50%', border: '1px solid rgba(255,255,255,0.1)' }}>
                <Upload size={34} color="#fff" strokeWidth={1.5} />
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#fff', marginBottom: 6 }}>Drop an offering memorandum</div>
                <div style={{ fontSize: 13, color: '#8e9192' }}>PDF · any broker format · any market</div>
              </div>
              <div style={{ fontSize: 10, fontFamily: 'JetBrains Mono,monospace', color: 'rgba(142,145,146,0.4)', letterSpacing: '0.1em' }}>or click to browse</div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Node graph */}
        <AnimatePresence>
          {file && (
            <motion.div key="graph" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              style={{
                position: 'relative',
                width: CANVAS_W, height: CANVAS_H,
                transform: `scale(${scale})`, transformOrigin: 'center center',
              }}
            >
              {/* Edges (SVG) */}
              <svg style={{ position: 'absolute', inset: 0, overflow: 'visible', pointerEvents: 'none' }} width={CANVAS_W} height={CANVAS_H}>
                <AnimatePresence>
                  {edges.map(e => <Edge key={e.id} from={e.from} to={e.to} lit={e.lit} />)}
                </AnimatePresence>
              </svg>

              {/* Node boxes */}
              <AnimatePresence>
                {nodes.map(n => {
                  const p = posMap.get(n.id)
                  if (!p) return null
                  return (
                    <motion.div key={n.id}
                      initial={{ opacity: 0, scale: 0.86 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                      style={{ position: 'absolute', left: p.x, top: p.y, transform: 'translate(-50%, -50%)' }}
                    >
                      <NodeBox n={n} active={n.id === active} />
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Background blobs */}
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: -1 }}>
          <div style={{ position: 'absolute', top: '-20%', left: '-10%', width: '45%', height: '60%', background: 'rgba(255,255,255,0.04)', borderRadius: '50%', filter: 'blur(140px)' }} />
          <div style={{ position: 'absolute', bottom: '-10%', right: '-5%', width: '38%', height: '50%', background: 'rgba(78,222,163,0.05)', borderRadius: '50%', filter: 'blur(120px)' }} />
        </div>
      </div>

      {/* ── Verdict reasoning panel — slides up when done ── */}
      <AnimatePresence>
        {isDone && state.verdict && (
          <motion.div
            key="reasoning"
            initial={{ y: 60, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 60, opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            style={{
              flexShrink: 0,
              borderTop: '1px solid rgba(255,255,255,0.08)',
              background: 'rgba(10,10,10,0.97)',
              backdropFilter: 'blur(24px)',
              padding: '18px 32px',
              maxHeight: 180,
              overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
              {/* Verdict badge */}
              <div style={{
                flexShrink: 0,
                padding: '6px 14px', borderRadius: 6,
                background: VC[state.verdict as VerdictVal].bg,
                border: '1px solid ' + VC[state.verdict as VerdictVal].border,
                boxShadow: VC[state.verdict as VerdictVal].glow,
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 8, fontFamily: 'JetBrains Mono,monospace', letterSpacing: '0.12em', color: VC[state.verdict as VerdictVal].text, marginBottom: 2 }}>VERDICT</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: VC[state.verdict as VerdictVal].text }}>{state.verdict}</div>
              </div>
              {/* Reasoning */}
              <p style={{ fontSize: 13, color: '#c4c7c8', lineHeight: 1.72, margin: 0, paddingTop: 2 }}>
                {extractReasoning(state.synthesisText) || 'Analysis complete. See full report for details.'}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Bottom bar ── */}
      <div style={{
        flexShrink: 0,
        borderTop: '1px solid rgba(255,255,255,0.05)',
        background: 'rgba(8,8,8,0.88)', backdropFilter: 'blur(20px)',
        padding: '13px 28px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
          {file && isRunning && (
            <motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.1, repeat: Infinity }}
              style={{ width: 6, height: 6, borderRadius: '50%', background: '#6366f1', flexShrink: 0 }} />
          )}
          {file && isDone && (
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
          )}
          <AnimatePresence mode="wait">
            <motion.p key={currentThought}
              initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
              style={{ fontSize: 13, color: '#8e9192', fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentThought}
            </motion.p>
          </AnimatePresence>
        </div>

        {file && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0 }}>
            <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono,monospace', color: 'rgba(142,145,146,0.5)' }}>
              {doneCount}/{SKILL_ORDER.length}
            </span>
            {isDone && (
              <button onClick={onBack} style={{ padding: '7px 16px', borderRadius: 7, fontSize: 12, fontWeight: 500, background: '#fff', color: '#141313', border: 'none', cursor: 'pointer' }}>
                New analysis
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
