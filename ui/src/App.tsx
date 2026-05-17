import { useState, useCallback, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { DemoView } from './components/DemoView'
import { IngestionView } from './components/IngestionView'
import { LiveIngestionView } from './components/LiveIngestionView'
// AnalysisView is available but currently IngestionView handles live analysis display
import type { AnalysisState, Verdict } from './types'

export const SKILL_ORDER = [
  'parse_om', 'owner_lookup', 'deed_lookup', 'portfolio_crawler',
  'permit_lookup', 'tax_lookup', 'violations_lookup',
  'comps_lookup', 'maturity_estimator', 'synthesize_analysis',
]

const SKILL_LABELS: Record<string, string> = {
  parse_om:            'Offering Memorandum',
  owner_lookup:        'Ownership',
  deed_lookup:         'Loan & Deed Records',
  portfolio_crawler:   'Owner Portfolio',
  permit_lookup:       'Building Permits',
  tax_lookup:          'Tax Status',
  violations_lookup:   'Code Violations',
  comps_lookup:        'Submarket Comps',
  maturity_estimator:  'Loan Pressure',
  synthesize_analysis: 'Final Analysis',
}

export interface AnalysisRecord {
  id: string
  property: string
  verdict: Verdict | null
  askingPrice: number | null
  status: 'running' | 'complete' | 'error'
}

const SEED_RECORDS: AnalysisRecord[] = []

function makeInitialState(): AnalysisState {
  const skills: AnalysisState['skills'] = {}
  SKILL_ORDER.forEach(name => { skills[name] = { name, label: SKILL_LABELS[name], status: 'idle' } })
  return { phase: 'idle', skills, synthesisText: '', verdict: null, propertyId: null, errorMessage: null }
}

export default function App() {
  const [view, setView]       = useState<'demo' | 'ingestion' | 'preview'>('demo')
  const [state, setState]     = useState<AnalysisState>(makeInitialState())
  const [file, setFile]       = useState<File | null>(null)
  const [records, setRecords] = useState<AnalysisRecord[]>(SEED_RECORDS)
  const abortRef              = useRef<AbortController | null>(null)
  const currentIdRef          = useRef<string | null>(null)

  const goBack = useCallback(() => {
    abortRef.current?.abort()
    setState(makeInitialState())
    setFile(null)
    setView('demo')
  }, [])

  const analyze = useCallback(async (f: File) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    const id = `${Date.now()}`
    currentIdRef.current = id

    setFile(f)
    setState(makeInitialState())
    const label = f.name.replace(/\.pdf$/i, '').replace(/[_-]/g, ' ')
    setRecords(prev => [{ id, property: label, verdict: null, askingPrice: null, status: 'running' }, ...prev])

    const form = new FormData()
    form.append('file', f)

    try {
      setState(s => ({ ...s, phase: 'uploading' }))
      const res = await fetch('/analyze', { method: 'POST', body: form, signal: ctrl.signal })
      if (!res.ok) throw new Error(`Server ${res.status}`)
      if (!res.body) throw new Error('No body')
      setState(s => ({ ...s, phase: 'analyzing' }))

      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try { applyEvent(JSON.parse(line.slice(6)), id) } catch { /**/ }
        }
      }
      setState(s => ({ ...s, phase: 'done' }))
    } catch (e: unknown) {
      if ((e as Error).name === 'AbortError') return
      setState(s => ({ ...s, phase: 'error', errorMessage: String(e) }))
      setRecords(prev => prev.map(r => r.id === id ? { ...r, status: 'error' } : r))
    }
  }, [])

  function applyEvent(ev: Record<string, unknown>, id: string) {
    const event = ev.event as string
    if (event === 'skill_start') {
      const sk = ev.skill as string
      setState(s => ({ ...s, skills: { ...s.skills, [sk]: { ...s.skills[sk], status: 'running' } } }))
    } else if (event === 'skill_complete') {
      const sk   = ev.skill as string
      const data = ev.data as Record<string, unknown> | undefined
      const pid  = ev.property_id as string | undefined
      if (sk === 'parse_om' && data) {
        const addr  = String(data.address ?? '')
        const price = data.asking_price ? Number(data.asking_price) : null
        if (addr) setRecords(prev => prev.map(r => r.id === id ? { ...r, property: addr, askingPrice: price } : r))
      }
      setState(s => ({
        ...s,
        propertyId: pid && pid !== 'unknown' ? pid : s.propertyId,
        skills: { ...s.skills, [sk]: { ...s.skills[sk], status: 'complete', data } },
      }))
    } else if (event === 'skill_error') {
      const sk = ev.skill as string
      setState(s => ({ ...s, skills: { ...s.skills, [sk]: { ...s.skills[sk], status: 'error' } } }))
    } else if (event === 'synthesis_chunk') {
      setState(s => ({ ...s, synthesisText: s.synthesisText + (ev.text as string) }))
    } else if (event === 'verdict') {
      const v = ev.recommendation as Verdict
      setState(s => ({ ...s, verdict: v }))
      setRecords(prev => prev.map(r => r.id === id ? { ...r, verdict: v, status: 'complete' } : r))
    } else if (event === 'error') {
      setState(s => ({ ...s, phase: 'error', errorMessage: ev.message as string }))
    }
  }

  return (
    <AnimatePresence mode="wait">
      {view === 'demo' && (
        <motion.div key="demo" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <DemoView records={records} onAnalyze={() => setView('ingestion')} onPreview={() => setView('preview')} />
        </motion.div>
      )}
      {view === 'ingestion' && (
        <motion.div key="ingestion" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <IngestionView state={state} file={file} onFile={analyze} onBack={goBack} />
        </motion.div>
      )}
      {view === 'preview' && (
        <motion.div key="preview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <LiveIngestionView onBack={() => setView('demo')} />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
