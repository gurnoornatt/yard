import { useCallback, useState } from 'react'
import { motion } from 'framer-motion'

function DocIllustration() {
  return (
    <svg width="120" height="155" viewBox="0 0 120 155" fill="none" style={{ opacity: 0.5 }}>
      <rect x="8" y="4" width="104" height="147" rx="6" fill="white" stroke="#D4D2CC" strokeWidth="1.5"/>
      <rect x="20" y="20" width="80" height="7" rx="3" fill="#E2E0DB"/>
      <rect x="20" y="34" width="60" height="4" rx="2" fill="#EEECE8"/>
      <rect x="20" y="44" width="75" height="4" rx="2" fill="#EEECE8"/>
      <rect x="20" y="54" width="50" height="4" rx="2" fill="#EEECE8"/>
      <rect x="20" y="70" width="80" height="1.5" rx="1" fill="#E2E0DB"/>
      <rect x="20" y="80" width="35" height="4" rx="2" fill="#EEECE8"/>
      <rect x="20" y="90" width="80" height="4" rx="2" fill="#EEECE8"/>
      <rect x="20" y="100" width="65" height="4" rx="2" fill="#EEECE8"/>
      <rect x="20" y="110" width="72" height="4" rx="2" fill="#EEECE8"/>
      <rect x="20" y="126" width="80" height="1.5" rx="1" fill="#E2E0DB"/>
      <rect x="20" y="133" width="50" height="4" rx="2" fill="#EEECE8"/>
      <rect x="20" y="141" width="35" height="4" rx="2" fill="#EEECE8"/>
    </svg>
  )
}

export function UploadView({ onFile, isLoading }: { onFile: (f: File) => void; isLoading: boolean }) {
  const [dragging, setDragging] = useState(false)

  const handle = useCallback((f: File) => {
    if (f.type === 'application/pdf' || f.name.endsWith('.pdf')) onFile(f)
  }, [onFile])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]; if (f) handle(f)
  }, [handle])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 48, width: '100%', maxWidth: 640 }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: 32, fontWeight: 650, letterSpacing: '-0.8px', color: 'var(--text)', marginBottom: 12, lineHeight: 1.2 }}>
          Drop an offering memorandum
        </h1>
        <p style={{ fontSize: 16, color: 'var(--text-2)', fontWeight: 400, lineHeight: 1.6, maxWidth: 440, margin: '0 auto' }}>
          Sentinel researches ownership, loans, permits, violations, and comps —
          then returns <strong style={{ color: 'var(--text)', fontWeight: 600 }}>PURSUE</strong>,{' '}
          <strong style={{ color: 'var(--text)', fontWeight: 600 }}>WATCHLIST</strong>, or{' '}
          <strong style={{ color: 'var(--text)', fontWeight: 600 }}>PASS</strong>.
        </p>
      </div>

      <motion.label
        animate={{ borderColor: dragging ? 'var(--accent)' : 'var(--border-2)', background: dragging ? 'rgba(124,58,237,0.03)' : 'var(--surface)' }}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          width: '100%', height: 260, borderRadius: 16,
          border: '1.5px dashed var(--border-2)',
          cursor: 'pointer', transition: 'all 0.15s',
          gap: 20,
        }}
      >
        <input type="file" accept=".pdf,application/pdf" style={{ display: 'none' }}
          onChange={e => { const f = e.target.files?.[0]; if (f) handle(f) }} />
        <DocIllustration />
        <div style={{ textAlign: 'center' }}>
          {isLoading ? (
            <p style={{ fontSize: 14, color: 'var(--text-2)', fontWeight: 500 }}>Uploading…</p>
          ) : (
            <>
              <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--text)' }}>
                {dragging ? 'Release to analyze' : 'Drop OM here or click to browse'}
              </p>
              <p style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>PDF only</p>
            </>
          )}
        </div>
      </motion.label>

      <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
        {['mccullough_om.pdf', 'blanco_om.pdf', 'culebra_om.pdf'].map(name => (
          <span key={name} style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'monospace' }}>
            demo: {name}
          </span>
        ))}
      </div>

      <p style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.05em' }}>
        NVIDIA Nemotron · Hermes Agent
      </p>
    </div>
  )
}
