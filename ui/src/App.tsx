import { useState, useCallback, useRef } from 'react'
import { IngestionView } from './components/IngestionView'
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

function makeInitialState(): AnalysisState {
  const skills: AnalysisState['skills'] = {}
  SKILL_ORDER.forEach(name => { skills[name] = { name, label: SKILL_LABELS[name], status: 'idle' } })
  return { phase: 'idle', skills, synthesisText: '', verdict: null, propertyId: null, errorMessage: null }
}

export default function App() {
  const [state, setState]   = useState<AnalysisState>(makeInitialState())
  const [file, setFile]     = useState<File | null>(null)
  const abortRef            = useRef<AbortController | null>(null)
  const currentIdRef        = useRef<string | null>(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setState(makeInitialState())
    setFile(null)
  }, [])

  const analyze = useCallback(async (f: File) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    currentIdRef.current = `${Date.now()}`

    setFile(f)
    setState(makeInitialState())

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
          try { applyEvent(JSON.parse(line.slice(6))) } catch { /**/ }
        }
      }
      setState(s => ({ ...s, phase: 'done' }))
    } catch (e: unknown) {
      if ((e as Error).name === 'AbortError') return
      setState(s => ({ ...s, phase: 'error', errorMessage: String(e) }))
    }
  }, [])

  function applyEvent(ev: Record<string, unknown>) {
    const event = ev.event as string
    if (event === 'skill_start') {
      const sk = ev.skill as string
      setState(s => ({ ...s, skills: { ...s.skills, [sk]: { ...s.skills[sk], status: 'running' } } }))
    } else if (event === 'skill_complete') {
      const sk   = ev.skill as string
      const data = ev.data as Record<string, unknown> | undefined
      const pid  = ev.property_id as string | undefined
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
    } else if (event === 'error') {
      setState(s => ({ ...s, phase: 'error', errorMessage: ev.message as string }))
    }
  }

  return <IngestionView state={state} file={file} onFile={analyze} onBack={reset} />
}
