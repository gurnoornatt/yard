import { motion } from 'framer-motion'
import { DocPanel } from './DocPanel'
import { DataFeed } from './DataFeed'
import { SynthesisPanel } from './SynthesisPanel'
import type { AnalysisState } from '../types'
import { SKILL_ORDER } from '../App'

export function AnalysisView({ state, file, onReset: _onReset, isAnalyzing }: {
  state: AnalysisState
  file: File | null
  onReset: () => void
  isAnalyzing: boolean
}) {
  const propertyData = state.skills.parse_om?.data as Record<string, unknown> | undefined
  const skills = SKILL_ORDER.map(n => state.skills[n]).filter(Boolean)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Property bar */}
      {propertyData && (
        <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
          style={{
            borderBottom: '1px solid var(--border)',
            padding: '12px 32px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: 'var(--surface)',
          }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
            <span style={{ fontWeight: 600, fontSize: 15, color: 'var(--text)', letterSpacing: '-0.2px' }}>
              {String(propertyData.address ?? '—')}
            </span>
            <span style={{ fontSize: 13, color: 'var(--text-3)' }}>
              {String(propertyData.units ?? '—')} units · {String(propertyData.year_built ?? '—')} · {String(propertyData.asset_class ?? '—')}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)' }}>
              {propertyData.asking_price ? `$${(Number(propertyData.asking_price) / 1_000_000).toFixed(2)}M` : '—'}
            </span>
            {state.verdict && <VerdictBadge verdict={state.verdict} />}
          </div>
        </motion.div>
      )}

      {/* Main 2-col layout */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: doc panel */}
        <div style={{ width: 280, flexShrink: 0, borderRight: '1px solid var(--border)', overflow: 'hidden' }}>
          <DocPanel file={file} propertyData={propertyData} isAnalyzing={isAnalyzing} />
        </div>

        {/* Center vertical connector line */}
        <div style={{ position: 'relative', width: 0 }}>
          <div style={{
            position: 'absolute', top: 0, bottom: 0, left: 0,
            width: 2, background: 'linear-gradient(to bottom, var(--accent) 0%, transparent 100%)',
            opacity: isAnalyzing ? 1 : 0.3, transition: 'opacity 0.5s',
          }} />
        </div>

        {/* Right: data feed */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
            <DataFeed skills={skills} isAnalyzing={isAnalyzing} />
          </div>
        </div>

        {/* Far right: synthesis panel */}
        {(state.synthesisText || !isAnalyzing) && (
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
            style={{ width: 380, flexShrink: 0, borderLeft: '1px solid var(--border)', overflow: 'auto' }}>
            <SynthesisPanel
              verdict={state.verdict}
              synthesisText={state.synthesisText}
              isStreaming={isAnalyzing && state.synthesisText.length > 0}
              allData={Object.fromEntries(
                Object.entries(state.skills).map(([k, v]) => [k, v?.data ?? null])
              )}
            />
          </motion.div>
        )}
      </div>
    </div>
  )
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    PURSUE:    { bg: 'var(--green-bg)',  color: 'var(--green)'  },
    WATCHLIST: { bg: 'var(--amber-bg)', color: 'var(--amber)'  },
    PASS:      { bg: 'var(--red-bg)',   color: 'var(--red)'    },
  }
  const s = styles[verdict] ?? { bg: '#f0f0f0', color: '#666' }
  return (
    <span style={{
      background: s.bg, color: s.color, fontWeight: 700, fontSize: 11,
      letterSpacing: '0.08em', padding: '4px 10px', borderRadius: 6,
    }}>
      {verdict}
    </span>
  )
}
