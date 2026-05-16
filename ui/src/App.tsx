import { useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { DropZone } from './components/DropZone'
import { InvestigationFeed } from './components/InvestigationFeed'
import { VerdictPanel } from './components/VerdictPanel'
import { PropertyHeader } from './components/PropertyHeader'
import type { AnalysisState, Verdict } from './types'

const SKILL_LABELS: Record<string, string> = {
  parse_om:           'Reading offering memorandum',
  owner_lookup:       'Tracing ownership chain',
  deed_lookup:        'Pulling loan & deed records',
  portfolio_crawler:  'Mapping owner portfolio',
  permit_lookup:      'Checking building permits',
  tax_lookup:         'Checking tax status',
  violations_lookup:  'Scanning code violations',
  comps_lookup:       'Pulling submarket comps',
  maturity_estimator: 'Estimating loan pressure',
  synthesize_analysis:'Synthesizing findings',
}

const SKILL_ORDER = [
  'parse_om', 'owner_lookup', 'deed_lookup', 'portfolio_crawler',
  'permit_lookup', 'tax_lookup', 'violations_lookup',
  'comps_lookup', 'maturity_estimator', 'synthesize_analysis',
]

function makeInitialState(): AnalysisState {
  const skills: AnalysisState['skills'] = {}
  SKILL_ORDER.forEach(name => {
    skills[name] = { name, label: SKILL_LABELS[name], status: 'idle' }
  })
  return { phase: 'idle', skills, synthesisText: '', verdict: null, propertyId: null, errorMessage: null }
}

export default function App() {
  const [state, setState] = useState<AnalysisState>(makeInitialState())
  const [fileName, setFileName] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setState(makeInitialState())
    setFileName(null)
  }, [])

  const analyze = useCallback(async (file: File) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setFileName(file.name)
    setState(s => ({ ...s, phase: 'uploading', synthesisText: '', verdict: null, errorMessage: null }))

    const form = new FormData()
    form.append('file', file)

    try {
      const res = await fetch('/analyze', { method: 'POST', body: form, signal: ctrl.signal })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      if (!res.body) throw new Error('No response body')

      setState(s => ({ ...s, phase: 'analyzing' }))

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try { handleEvent(JSON.parse(line.slice(6))) } catch { /**/ }
        }
      }
      setState(s => ({ ...s, phase: 'done' }))
    } catch (e: unknown) {
      if ((e as Error).name === 'AbortError') return
      setState(s => ({ ...s, phase: 'error', errorMessage: String(e) }))
    }
  }, [])

  function handleEvent(ev: Record<string, unknown>) {
    const event = ev.event as string
    if (event === 'skill_start') {
      const skill = ev.skill as string
      setState(s => ({ ...s, skills: { ...s.skills, [skill]: { ...s.skills[skill], status: 'running' } } }))
    } else if (event === 'skill_complete') {
      const skill = ev.skill as string
      const pid = ev.property_id as string | undefined
      setState(s => ({
        ...s,
        propertyId: pid && pid !== 'unknown' ? pid : s.propertyId,
        skills: { ...s.skills, [skill]: { ...s.skills[skill], status: 'complete', data: ev.data as Record<string, unknown> | undefined } },
      }))
    } else if (event === 'skill_error') {
      const skill = ev.skill as string
      setState(s => ({ ...s, skills: { ...s.skills, [skill]: { ...s.skills[skill], status: 'error' } } }))
    } else if (event === 'synthesis_chunk') {
      setState(s => ({ ...s, synthesisText: s.synthesisText + (ev.text as string) }))
    } else if (event === 'verdict') {
      setState(s => ({ ...s, verdict: ev.recommendation as Verdict }))
    } else if (event === 'error') {
      setState(s => ({ ...s, phase: 'error', errorMessage: ev.message as string }))
    }
  }

  const hasResults = state.phase === 'analyzing' || state.phase === 'done'
  const isAnalyzing = state.phase === 'analyzing' || state.phase === 'uploading'
  const propertyData = state.skills.parse_om?.data as Record<string, unknown> | undefined

  return (
    <div className="min-h-screen bg-[#080808] flex flex-col">
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between sticky top-0 bg-[#080808]/90 backdrop-blur z-50">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 rounded bg-white flex items-center justify-center">
            <span className="text-black text-[10px] font-bold">S</span>
          </div>
          <span className="text-white font-semibold tracking-tight">Sentinel</span>
          <span className="text-white/20 text-sm hidden sm:inline">OM Analyzer</span>
        </div>
        <div className="flex items-center gap-4">
          {fileName && <span className="text-white/30 text-xs font-mono truncate max-w-48">{fileName}</span>}
          {hasResults && (
            <button onClick={reset} className="text-xs text-white/40 hover:text-white/70 transition-colors border border-white/10 rounded px-3 py-1">
              New analysis
            </button>
          )}
        </div>
      </header>

      <AnimatePresence mode="wait">
        {state.phase === 'idle' && (
          <motion.div key="idle" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }}
            className="flex-1 flex flex-col items-center justify-center px-4 gap-8">
            <div className="text-center">
              <h1 className="text-4xl font-semibold text-white tracking-tight mb-3">Drop an offering memorandum</h1>
              <p className="text-white/40 text-sm max-w-md leading-relaxed">
                Sentinel researches ownership, loans, permits, violations, and comps — then returns PURSUE, WATCHLIST, or PASS.
              </p>
            </div>
            <DropZone onFile={analyze} />
            <p className="text-white/15 text-xs font-mono">Powered by NVIDIA Nemotron · Hermes Agent</p>
          </motion.div>
        )}

        {(hasResults || state.phase === 'uploading') && (
          <motion.div key="analysis" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex-1 flex flex-col lg:flex-row overflow-hidden">
            <div className="flex-1 border-r border-white/5 flex flex-col overflow-hidden">
              {propertyData && <PropertyHeader data={propertyData} verdict={state.verdict} />}
              <div className="flex-1 overflow-y-auto p-6">
                <InvestigationFeed skills={SKILL_ORDER.map(n => state.skills[n]).filter(Boolean)} isAnalyzing={isAnalyzing} />
              </div>
            </div>
            <div className="w-full lg:w-[440px] border-t lg:border-t-0 border-white/5 overflow-y-auto">
              <VerdictPanel verdict={state.verdict} synthesisText={state.synthesisText}
                isStreaming={isAnalyzing && state.synthesisText.length > 0} phase={state.phase} />
            </div>
          </motion.div>
        )}

        {state.phase === 'error' && (
          <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <p className="text-red-400 mb-4 text-sm">{state.errorMessage}</p>
              <button onClick={reset} className="text-white/50 hover:text-white text-sm underline">Try again</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
