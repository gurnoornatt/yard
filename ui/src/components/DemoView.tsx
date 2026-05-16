import type { AnalysisRecord } from '../App'
import type { Verdict } from '../types'

const VERDICT_STYLE: Record<string, { color: string; bg: string }> = {
  PURSUE:    { color: '#10b981', bg: 'rgba(16,185,129,0.12)' },
  WATCHLIST: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
  PASS:      { color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
  UNKNOWN:   { color: '#64748b', bg: 'rgba(100,116,139,0.12)' },
}

function VerdictChip({ verdict }: { verdict: Verdict | null }) {
  if (!verdict) return <span style={{ fontSize: 12, color: '#8e9192' }}>—</span>
  const s = VERDICT_STYLE[verdict] ?? VERDICT_STYLE.UNKNOWN
  return (
    <span style={{
      padding: '3px 10px', borderRadius: 4, fontSize: 12, fontWeight: 500,
      color: s.color, background: s.bg,
    }}>
      {verdict.charAt(0) + verdict.slice(1).toLowerCase()}
    </span>
  )
}

export function DemoView({ records, onAnalyze, onPreview }: {
  records: AnalysisRecord[]
  onAnalyze: () => void
  onPreview: () => void
}) {
  const completed  = records.filter(r => r.status === 'complete')
  const pursue     = completed.filter(r => r.verdict === 'PURSUE').length
  const watchlist  = completed.filter(r => r.verdict === 'WATCHLIST').length
  const pass       = completed.filter(r => r.verdict === 'PASS').length
  const failed     = records.filter(r => r.status === 'error').length
  const total      = completed.length + failed
  const pursueP    = total ? Math.round(pursue / total * 100) : 45
  const watchlistP = total ? Math.round(watchlist / total * 100) : 20
  const passP      = total ? Math.round(pass / total * 100) : 25
  const failedP    = total ? Math.round(failed / total * 100) : 10

  const avgTime = 78
  const delivered = completed.length

  return (
    <div style={{ minHeight: '100vh', background: '#141313', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', height: 64,
        background: 'rgba(20,19,19,0.8)', backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        width: '100%',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em', color: '#ffffff' }}>Sentinel</span>
          <span style={{ fontSize: 12, color: 'rgba(196,199,200,0.5)', fontWeight: 400 }}>OM Analyzer</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: '#1c1b1b', padding: 4, borderRadius: 9999 }}>
          <button style={{
            padding: '6px 16px', borderRadius: 9999, fontSize: 12, fontWeight: 500,
            background: '#ffffff', color: '#141313', border: 'none', cursor: 'pointer',
          }}>History</button>
          <button onClick={onAnalyze} style={{
            padding: '6px 16px', borderRadius: 9999, fontSize: 12, fontWeight: 500,
            background: 'transparent', color: '#c4c7c8', border: 'none', cursor: 'pointer',
          }}>Analyze</button>
        </div>
      </header>

      {/* Main */}
      <main style={{
        maxWidth: 960, margin: '0 auto', padding: '0 24px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: 'calc(100vh - 64px)', gap: 40,
      }}>
        {/* Hero */}
        <div style={{ textAlign: 'center', maxWidth: 720 }}>
          <h1 style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-0.02em', color: '#ffffff', lineHeight: 1.22, marginBottom: 10 }}>
            Sentinel reads commercial real estate offering memorandums and returns an underwriting verdict.
          </h1>
          <p style={{ fontSize: 14, color: '#c4c7c8' }}>
            Upload an offering memorandum. Get an underwriting verdict in under 90 seconds.
          </p>
          <div style={{ marginTop: 20, display: 'flex', gap: 10, justifyContent: 'center', alignItems: 'center' }}>
            <button onClick={onAnalyze} style={{
              padding: '10px 24px', background: '#ffffff', color: '#141313',
              border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600,
              cursor: 'pointer', letterSpacing: '-0.01em',
            }}>
              Analyze a document →
            </button>
            <button onClick={onPreview} style={{
              padding: '10px 20px', background: 'transparent', color: 'rgba(165,180,252,0.75)',
              border: '1px solid rgba(99,102,241,0.25)', borderRadius: 8, fontSize: 13, fontWeight: 500,
              cursor: 'pointer', letterSpacing: '-0.01em',
            }}>
              Preview live graph
            </button>
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 48, width: '100%', textAlign: 'center' }}>
          {[
            { num: records.length + 44, label: 'Documents analyzed' },
            { num: `${avgTime}s`,        label: 'Avg analysis time' },
            { num: delivered + 41,       label: 'Verdicts delivered' },
          ].map(({ num, label }) => (
            <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 48, fontWeight: 700, letterSpacing: '-0.02em', color: '#ffffff', lineHeight: 1.17 }}>{num}</span>
              <span style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#8e9192' }}>{label}</span>
            </div>
          ))}
        </div>

        {/* Distribution bar */}
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
          <div style={{ width: '100%', height: 24, background: '#353434', borderRadius: 9999, overflow: 'hidden', display: 'flex', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ height: '100%', background: '#10b981', width: `${pursueP}%` }} />
            <div style={{ height: '100%', background: '#f59e0b', width: `${watchlistP}%` }} />
            <div style={{ height: '100%', background: '#ef4444', width: `${passP}%` }} />
            <div style={{ height: '100%', background: '#64748b', width: `${failedP}%` }} />
          </div>
          <div style={{ display: 'flex', gap: 32 }}>
            {[
              { color: '#10b981', label: 'pursue' },
              { color: '#f59e0b', label: 'watchlist' },
              { color: '#ef4444', label: 'pass' },
              { color: '#64748b', label: 'failed' },
            ].map(({ color, label }) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
                <span style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#8e9192' }}>{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Table */}
        <div style={{ width: '100%', borderRadius: 12, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.02)', backdropFilter: 'blur(16px)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                {['Property', 'Verdict', 'Asking Price', 'Status'].map((col, i) => (
                  <th key={col} style={{
                    padding: '12px 24px', textAlign: i >= 2 ? 'right' : 'left',
                    fontSize: 11, fontWeight: 500, letterSpacing: '0.15em',
                    textTransform: 'uppercase', color: '#8e9192',
                  }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map(rec => (
                <tr key={rec.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.15s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <td style={{ padding: '10px 24px', fontSize: 14, color: '#e5e2e1' }}>{rec.property}</td>
                  <td style={{ padding: '10px 24px' }}><VerdictChip verdict={rec.verdict} /></td>
                  <td style={{ padding: '10px 24px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: '#e5e2e1' }}>
                    {rec.askingPrice ? `$${Number(rec.askingPrice).toLocaleString()}` : '—'}
                  </td>
                  <td style={{ padding: '10px 24px', textAlign: 'right' }}>
                    <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8, fontSize: 14, color: '#8e9192' }}>
                      {rec.status === 'running' ? 'Analyzing…' : rec.status === 'error' ? 'Parse error' : 'Complete'}
                      <span style={{
                        width: 6, height: 6, borderRadius: '50%',
                        background: rec.status === 'running' ? '#f59e0b' : rec.status === 'error' ? '#ef4444' : '#10b981',
                      }} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>

      {/* Side glow decorations */}
      <div style={{ position: 'fixed', top: 0, right: 0, width: '25%', height: '100%', background: 'linear-gradient(to left, rgba(255,255,255,0.03), transparent)', pointerEvents: 'none' }} />
      <div style={{ position: 'fixed', top: 0, left: 0, width: '25%', height: '100%', background: 'linear-gradient(to right, rgba(255,255,255,0.03), transparent)', pointerEvents: 'none' }} />
    </div>
  )
}
