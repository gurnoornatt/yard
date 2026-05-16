import { motion } from 'framer-motion'

function DocPlaceholder({ isAnalyzing }: { isAnalyzing: boolean }) {
  return (
    <motion.div
      animate={{ opacity: isAnalyzing ? [0.4, 0.7, 0.4] : 0.6 }}
      transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      style={{
        width: '100%', aspectRatio: '8.5/11',
        background: 'var(--surface)',
        borderRadius: 8, border: '1px solid var(--border)',
        padding: 20, display: 'flex', flexDirection: 'column', gap: 10,
      }}
    >
      {/* Header block */}
      <div style={{ height: 10, width: '60%', background: 'var(--border)', borderRadius: 3 }} />
      <div style={{ height: 6, width: '40%', background: '#EEECE8', borderRadius: 3 }} />
      <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
      {/* Content lines */}
      {[80, 65, 72, 55, 78, 60, 70].map((w, i) => (
        <div key={i} style={{ height: 6, width: `${w}%`, background: '#EEECE8', borderRadius: 3 }} />
      ))}
      <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
      <div style={{ height: 8, width: '50%', background: 'var(--border)', borderRadius: 3 }} />
      {[70, 62, 75, 55].map((w, i) => (
        <div key={i} style={{ height: 6, width: `${w}%`, background: '#EEECE8', borderRadius: 3 }} />
      ))}
      <div style={{ flex: 1 }} />
      <div style={{ height: 6, width: '45%', background: '#EEECE8', borderRadius: 3 }} />
      <div style={{ height: 6, width: '30%', background: '#EEECE8', borderRadius: 3 }} />
    </motion.div>
  )
}

export function DocPanel({ file, propertyData, isAnalyzing }: {
  file: File | null
  propertyData: Record<string, unknown> | undefined
  isAnalyzing: boolean
}) {
  return (
    <div style={{ height: '100%', padding: '24px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        Document
      </p>

      {file && (
        <p style={{ fontSize: 12, color: 'var(--text-2)', fontFamily: 'monospace', wordBreak: 'break-all' }}>
          {file.name}
        </p>
      )}

      <DocPlaceholder isAnalyzing={isAnalyzing} />

      {/* Scanning indicator */}
      {isAnalyzing && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 12px', borderRadius: 8,
            background: 'rgba(124,58,237,0.06)',
            border: '1px solid rgba(124,58,237,0.12)',
          }}
        >
          <motion.div
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ duration: 1.2, repeat: Infinity }}
            style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)' }}
          />
          <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>Analyzing…</span>
        </motion.div>
      )}
    </div>
  )
}
