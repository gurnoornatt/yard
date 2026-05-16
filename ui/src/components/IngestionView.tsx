import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Check, BarChart2, Gavel, Upload, CheckCircle } from 'lucide-react'
import type { AnalysisState, Verdict } from '../types'

type StepStatus = 'pending' | 'active' | 'complete'

const VERDICT_CONFIG: Record<string, { color: string; bg: string; border: string; glow: string }> = {
  PURSUE:    { color: '#10b981', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.4)', glow: 'rgba(16,185,129,0.15)' },
  WATCHLIST: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.4)', glow: 'rgba(245,158,11,0.15)' },
  PASS:      { color: '#ef4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.4)', glow: 'rgba(239,68,68,0.15)' },
}

function deriveSteps(state: AnalysisState): StepStatus[] {
  const sk = state.skills

  const parseSt = sk.parse_om?.status ?? 'idle'
  const parse: StepStatus =
    parseSt === 'complete' ? 'complete' :
    parseSt === 'running'  ? 'active'   :
    state.phase !== 'idle' ? 'active'   : 'pending'

  const lookups = ['owner_lookup', 'deed_lookup', 'portfolio_crawler', 'permit_lookup', 'tax_lookup', 'violations_lookup', 'comps_lookup', 'maturity_estimator']
  const anyRunning = lookups.some(n => sk[n]?.status === 'running')
  const anyStarted = lookups.some(n => (sk[n]?.status ?? 'idle') !== 'idle')
  const allDone    = lookups.every(n => ['complete', 'error'].includes(sk[n]?.status ?? 'idle'))
  const extract: StepStatus =
    allDone && anyStarted ? 'complete' :
    anyRunning || anyStarted ? 'active' : 'pending'

  const synthSt = sk.synthesize_analysis?.status ?? 'idle'
  const analyze: StepStatus =
    state.verdict ? 'complete' :
    synthSt === 'running' || state.synthesisText.length > 0 ? 'active' : 'pending'

  const verdict: StepStatus =
    state.verdict ? 'complete' :
    analyze === 'complete' ? 'active' : 'pending'

  return [parse, extract, analyze, verdict]
}

const STEPS = [
  { label: 'PARSE',   Icon: FileText },
  { label: 'EXTRACT', Icon: BarChart2 },
  { label: 'ANALYZE', Icon: BarChart2 },
  { label: 'VERDICT', Icon: Gavel },
]

function PipelineStep({ label, Icon, status, isLast }: {
  label: string; Icon: React.ElementType; status: StepStatus; isLast: boolean
}) {
  const isActive   = status === 'active'
  const isComplete = status === 'complete'

  return (
    <div style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: isActive ? 48 : 40, height: isActive ? 48 : 40,
          borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: isActive ? 'rgba(255,255,255,0.08)' : isComplete ? 'rgba(78,222,163,0.1)' : 'rgba(255,255,255,0.03)',
          border: isActive ? '1px solid rgba(255,255,255,0.3)' : isComplete ? '1px solid rgba(78,222,163,0.5)' : '1px solid rgba(255,255,255,0.08)',
          boxShadow: isActive ? '0 0 20px rgba(255,255,255,0.15)' : 'none',
          transition: 'all 0.3s',
        }}>
          {isComplete
            ? <Check size={isActive ? 20 : 16} color="#4edea3" />
            : <Icon size={isActive ? 22 : 18} color={isActive ? '#ffffff' : '#8e9192'} />
          }
        </div>
        <span style={{
          fontSize: 11, fontWeight: isActive ? 700 : 500,
          letterSpacing: '0.15em', fontFamily: 'JetBrains Mono, monospace',
          color: isActive ? '#ffffff' : isComplete ? '#4edea3' : 'rgba(142,145,146,0.4)',
          transition: 'color 0.3s',
        }}>{label}</span>
      </div>
      {!isLast && (
        <div style={{
          flex: 1, height: 2, margin: '0 12px', marginBottom: 28,
          background: isComplete ? '#ffffff' : 'rgba(255,255,255,0.06)',
          boxShadow: isComplete ? '0 0 12px rgba(255,255,255,0.2)' : 'none',
          transition: 'all 0.4s',
        }} />
      )}
    </div>
  )
}

export function IngestionView({ state, file, onFile, onBack }: {
  state: AnalysisState
  file: File | null
  onFile: (f: File) => void
  onBack: () => void
}) {
  const [dragging, setDragging] = useState(false)
  const steps = deriveSteps(state)
  const isProcessing = state.phase === 'uploading' || state.phase === 'analyzing'
  const isDone       = state.phase === 'done'

  const completedSkillCount = Object.values(state.skills).filter(s => s.status === 'complete').length
  const progress =
    isDone ? 100 :
    state.phase === 'uploading' ? 18 :
    state.phase === 'analyzing' ? 18 + Math.round((completedSkillCount / 10) * 80) : 0

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }
  const handleClick = () => {
    if (isProcessing) return
    const inp = document.createElement('input')
    inp.type = 'file'; inp.accept = '.pdf'
    inp.onchange = (e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) onFile(f) }
    inp.click()
  }

  const verdict = state.verdict
  const vc = verdict ? VERDICT_CONFIG[verdict] : null

  return (
    <div className="mesh-bg" style={{ minHeight: '100vh', background: '#080808', display: 'flex', flexDirection: 'column' }}>

      {/* Header */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', height: 64,
        background: 'rgba(8,8,8,0.6)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)', width: '100%',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em', color: '#ffffff' }}>Sentinel</span>
          <span style={{ fontSize: 12, color: 'rgba(196,199,200,0.5)', fontWeight: 400 }}>OM Analyzer</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(255,255,255,0.05)', padding: 4, borderRadius: 9999 }}>
          <button onClick={onBack} style={{
            padding: '6px 16px', borderRadius: 9999, fontSize: 12, fontWeight: 500,
            background: 'transparent', color: '#c4c7c8', border: 'none', cursor: 'pointer',
          }}>History</button>
          <button style={{
            padding: '6px 16px', borderRadius: 9999, fontSize: 12, fontWeight: 500,
            background: '#ffffff', color: '#141313', border: 'none', cursor: 'pointer',
          }}>Analyze</button>
        </div>
      </header>

      {/* Main */}
      <main style={{
        flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', padding: '32px 24px', maxWidth: 800, margin: '0 auto', width: '100%', gap: 0,
      }}>
        {/* Headline */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-0.02em', color: '#ffffff', lineHeight: 1.22 }}>
            Drop a document. Watch it get analyzed.
          </h1>
          <p style={{ fontSize: 14, color: '#c4c7c8', opacity: 0.6, marginTop: 8 }}>
            Institutional-grade extraction and autonomous risk modeling.
          </p>
        </div>

        {/* Upload zone */}
        <div
          className="glass"
          onClick={handleClick}
          onDrop={handleDrop}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          style={{
            width: '100%', minHeight: 320,
            border: `2px dashed ${dragging ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.1)'}`,
            borderRadius: 16,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            padding: 32, cursor: isProcessing ? 'default' : 'pointer',
            transition: 'border-color 0.2s',
            gap: 24,
          }}
        >
          {/* Upload icon — always show at top */}
          {!file && (
            <div style={{
              padding: 16, background: 'rgba(255,255,255,0.05)',
              borderRadius: '50%', border: '1px solid rgba(255,255,255,0.1)',
            }}>
              <Upload size={40} color="#ffffff" />
            </div>
          )}

          {/* File progress card */}
          <AnimatePresence>
            {file && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                style={{
                  width: '100%', maxWidth: 400,
                  background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(20px)',
                  borderRadius: 16, padding: 16, border: '1px solid rgba(255,255,255,0.1)',
                }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <FileText size={20} color="#4edea3" />
                    <div>
                      <p style={{ fontSize: 12, fontWeight: 500, color: '#e5e2e1' }}>{file.name}</p>
                      <p style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: 'rgba(196,199,200,0.5)' }}>
                        {(file.size / 1024 / 1024).toFixed(1)} MB
                      </p>
                    </div>
                  </div>
                  <span style={{ fontSize: 12, fontFamily: 'JetBrains Mono, monospace', color: '#4edea3' }}>{progress}%</span>
                </div>
                <div style={{ height: 6, width: '100%', background: 'rgba(255,255,255,0.08)', borderRadius: 9999, overflow: 'hidden' }}>
                  <motion.div
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.5, ease: 'easeOut' }}
                    style={{
                      height: '100%', background: '#4edea3', borderRadius: 9999,
                      boxShadow: '0 0 10px rgba(78,222,163,0.5)',
                    }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Status text */}
          <p style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'rgba(196,199,200,0.4)', fontFamily: 'JetBrains Mono, monospace' }}>
            {!file ? 'Drop PDF here or click to browse' : isProcessing ? 'Proprietary Agent-Lead Analysis in Progress' : isDone ? 'Analysis complete' : 'Ready'}
          </p>
        </div>

        {/* Pipeline stepper */}
        <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 40, padding: '0 8px' }}>
          {STEPS.map(({ label, Icon }, i) => (
            <PipelineStep
              key={label}
              label={label}
              Icon={i === 2 ? BarChart2 : Icon}
              status={steps[i]}
              isLast={i === STEPS.length - 1}
            />
          ))}
        </div>

        {/* Verdict pill */}
        <AnimatePresence>
          {vc && verdict && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
              style={{ marginTop: 40, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <p style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'rgba(142,145,146,0.6)', fontFamily: 'JetBrains Mono, monospace' }}>
                Initial Determination
              </p>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '14px 28px',
                background: vc.bg, border: `1px solid ${vc.border}`,
                borderRadius: 9999,
                boxShadow: `0 10px 40px ${vc.glow}`,
              }}>
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: `${vc.color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <CheckCircle size={18} color={vc.color} fill={vc.color} />
                </div>
                <span style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.01em', color: vc.color, textTransform: 'uppercase' }}>
                  {verdict.charAt(0) + verdict.slice(1).toLowerCase()}
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Background blobs */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: -10, overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: '-15%', left: '-10%', width: '50%', height: '50%', background: 'rgba(255,255,255,0.06)', borderRadius: '50%', filter: 'blur(140px)' }} />
        <div style={{ position: 'absolute', bottom: '-10%', right: '-10%', width: '40%', height: '40%', background: 'rgba(78,222,163,0.07)', borderRadius: '50%', filter: 'blur(120px)' }} />
      </div>
    </div>
  )
}
