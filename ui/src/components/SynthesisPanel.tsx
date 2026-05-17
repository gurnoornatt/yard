import { motion } from 'framer-motion'
import type { Verdict } from '../types'

const VERDICT_CONFIG: Record<string, { label: string; bg: string; color: string; border: string }> = {
  PURSUE:    { label: 'PURSUE',    bg: 'var(--green-bg)',  color: 'var(--green)',  border: '#86efac' },
  WATCHLIST: { label: 'WATCHLIST', bg: 'var(--amber-bg)', color: 'var(--amber)', border: '#fcd34d' },
  PASS:      { label: 'PASS',      bg: 'var(--red-bg)',   color: 'var(--red)',   border: '#fca5a5' },
  UNKNOWN:   { label: 'UNKNOWN',   bg: 'rgba(100,116,139,0.1)', color: '#64748b', border: '#64748b' },
}

function extractReasoning(text: string): { reasoning: string; rest: string } {
  const idx = text.indexOf('## Bottom-Line Recommendation')
  if (idx === -1) return { reasoning: '', rest: text }

  const afterHeader = text.slice(idx + '## Bottom-Line Recommendation'.length).trimStart()
  // Find where the next section starts (if any)
  const nextSection = afterHeader.indexOf('\n## ')
  const reasoningBlock = nextSection !== -1 ? afterHeader.slice(0, nextSection) : afterHeader
  const rest = text.slice(0, idx).trimEnd()

  // Strip the leading PURSUE/WATCHLIST/PASS word so the reasoning reads as plain prose
  const cleaned = reasoningBlock.replace(/^(PURSUE|WATCHLIST|PASS)\s*/i, '').trim()
  return { reasoning: cleaned, rest }
}

function renderSections(text: string) {
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
      <p key={i} style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.7 }}>
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
  const { reasoning, rest } = extractReasoning(synthesisText)

  return (
    <div style={{ padding: '24px 24px' }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}>
        Analysis
      </p>

      {/* Verdict badge */}
      {c && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          style={{
            background: c.bg, border: `1px solid ${c.border}`,
            borderRadius: 10, padding: '14px 16px', marginBottom: 16,
          }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: reasoning ? 10 : 0 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: c.color, flexShrink: 0 }} />
            <span style={{ fontWeight: 800, fontSize: 13, letterSpacing: '0.1em', color: c.color }}>
              {c.label}
            </span>
          </div>

          {/* Reasoning block — shows the "why" right under the verdict */}
          {reasoning && (
            <p style={{
              fontSize: 13, color: 'var(--text-2)', lineHeight: 1.7,
              margin: 0, paddingTop: 2,
            }}>
              {reasoning}
            </p>
          )}
        </motion.div>
      )}

      {/* Rest of analysis sections */}
      {synthesisText ? (
        <div>
          {renderSections(rest)}
          {isStreaming && (
            <motion.span
              animate={{ opacity: [1, 0, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
              style={{ display: 'inline-block', width: 2, height: 14, background: 'var(--accent)', marginLeft: 2, verticalAlign: 'text-bottom' }}
            />
          )}
        </div>
      ) : (
        <motion.div
          animate={{ opacity: [0.3, 0.8, 0.3] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          style={{ fontSize: 13, color: 'var(--text-3)' }}
        >
          Waiting for research to complete…
        </motion.div>
      )}
    </div>
  )
}
