import { motion, AnimatePresence } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import type { Verdict } from '../types'

const config = {
  PURSUE:    { label: 'PURSUE',    bg: 'bg-emerald-500', text: 'text-emerald-400', border: 'border-emerald-500/20', glow: 'shadow-emerald-500/10' },
  WATCHLIST: { label: 'WATCHLIST', bg: 'bg-amber-500',   text: 'text-amber-400',   border: 'border-amber-500/20',   glow: 'shadow-amber-500/10'   },
  PASS:      { label: 'PASS',      bg: 'bg-red-500',     text: 'text-red-400',     border: 'border-red-500/20',     glow: 'shadow-red-500/10'     },
  UNKNOWN:   { label: 'UNKNOWN',   bg: 'bg-white/20',    text: 'text-white/50',    border: 'border-white/10',       glow: '' },
}

function formatSynthesis(text: string) {
  return text.split('\n').map((line, i) => {
    if (line.startsWith('## ')) {
      return <h3 key={i} className="text-white/80 text-xs font-semibold uppercase tracking-widest mt-5 mb-2 first:mt-0">{line.slice(3)}</h3>
    }
    if (line.trim() === '') return <div key={i} className="h-1" />
    return <p key={i} className="text-white/55 text-sm leading-relaxed">{line}</p>
  })
}

export function VerdictPanel({ verdict, synthesisText, isStreaming, phase }: {
  verdict: Verdict | null
  synthesisText: string
  isStreaming: boolean
  phase: string
}) {
  const c = verdict ? config[verdict] : null
  const analyzing = phase === 'analyzing' || phase === 'uploading'

  return (
    <div className="p-6 flex flex-col gap-6 h-full">
      <p className="text-white/20 text-xs font-mono uppercase tracking-widest">Analysis</p>

      <AnimatePresence mode="wait">
        {!verdict && analyzing && (
          <motion.div key="waiting" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-white/30 text-sm">
            <Loader2 size={14} className="animate-spin" />
            <span>Researching...</span>
          </motion.div>
        )}

        {verdict && c && (
          <motion.div key="verdict" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
            <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border ${c.border} bg-white/[0.03] shadow-lg ${c.glow}`}>
              <div className={`w-2 h-2 rounded-full ${c.bg}`} />
              <span className={`text-sm font-bold tracking-wider ${c.text}`}>{c.label}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {(synthesisText || isStreaming) && (
        <div className="flex-1 min-h-0">
          <div className="prose-sm max-w-none">
            {formatSynthesis(synthesisText)}
            {isStreaming && (
              <span className="inline-block w-0.5 h-4 bg-white/40 ml-0.5 animate-pulse align-middle" />
            )}
          </div>
        </div>
      )}

      {!synthesisText && !analyzing && (
        <p className="text-white/20 text-sm">Verdict will appear here</p>
      )}
    </div>
  )
}
