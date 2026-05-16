import { motion } from 'framer-motion'
import type { Verdict } from '../types'

const VERDICT_CONFIG = {
  PURSUE:    { label: 'PURSUE',    bg: 'var(--green-bg)',  color: 'var(--green)',  border: '#86efac' },
  WATCHLIST: { label: 'WATCHLIST', bg: 'var(--amber-bg)', color: 'var(--amber)', border: '#fcd34d' },
  PASS:      { label: 'PASS',      bg: 'var(--red-bg)',   color: 'var(--red)',   border: '#fca5a5' },
}

function renderSynthesis(text: string) {
  return text.split('\n').map((line, i) => {
    if (line.startsWith('## ')) {
      return (
        <h3 key={i} style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
          textTransform: 'uppercase', color: 'var(--text-3)',
          marginTop: i === 0 ? 0 : 20, marginBottom: 6,
        }}>
          {line.slice(3)}
        </h3>
      )
    }
    if (!line.trim()) return <div key={i} style={{ height: 4 }} />
    return (
      <p key={i} style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.65 }}>
        {line}
      </p>
    )
  })
}

export function SynthesisPanel({ verdict, synthesisText, isStreaming }: {
  verdict: Verdict | null
  synthesisText: string
  isStreaming: boolean
}) {
  const c = verdict ? VERDICT_CONFIG[verdict] : null

  return (
    <div style={{ padding: '24px 24px' }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}>
        Analysis
      </p>

      {c && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          style={{
            background: c.bg, border: `1px solid ${c.border}`,
            borderRadius: 10, padding: '12px 16px', marginBottom: 20,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: c.color, flexShrink: 0 }} />
          <span style={{ fontWeight: 800, fontSize: 13, letterSpacing: '0.1em', color: c.color }}>
            {c.label}
          </span>
        </motion.div>
      )}

      {synthesisText ? (
        <div>
          {renderSynthesis(synthesisText)}
          {isStreaming && (
            <motion.span
              animate={{ opacity: [1, 0, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
              style={{ display: 'inline-block', width: 2, height: 14, background: 'var(--accent)', marginLeft: 2, verticalAlign: 'text-bottom' }}
            />
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <motion.div
            animate={{ opacity: [0.3, 0.8, 0.3] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            style={{ fontSize: 13, color: 'var(--text-3)' }}
          >
            Waiting for research to complete…
          </motion.div>
        </div>
      )}
    </div>
  )
}
