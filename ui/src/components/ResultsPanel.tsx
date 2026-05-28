import { motion } from 'framer-motion'
import type { AnalysisState } from '../types'

// ─── Verdict colors ───────────────────────────────────────────────────────────

const VC: Record<string, { color: string; bg: string; border: string }> = {
  PURSUE:    { color: '#10b981', bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.3)'  },
  WATCHLIST: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)'  },
  PASS:      { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.3)'   },
  UNKNOWN:   { color: '#64748b', bg: 'rgba(100,116,139,0.1)',  border: 'rgba(100,116,139,0.3)' },
}

// ─── Small components ─────────────────────────────────────────────────────────

function SourceTag({ label }: { label: string }) {
  return (
    <span style={{
      display: 'inline-block', fontSize: 10, padding: '2px 9px', borderRadius: 9999,
      background: 'rgba(232,115,58,0.08)', color: 'rgba(232,115,58,0.6)',
      border: '1px solid rgba(232,115,58,0.14)', letterSpacing: '0.02em', whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  )
}

function DataRow({
  label, value, source, note, highlight, last,
}: {
  label: string; value: string | null; source: string
  note?: string; highlight?: boolean; last?: boolean
}) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '140px 1fr', gap: '0 24px',
      padding: '16px 0',
      borderBottom: last ? 'none' : '1px solid rgba(255,255,255,0.05)',
    }}>
      <span style={{ fontSize: 13, color: '#5c5550', alignSelf: 'start', paddingTop: 2 }}>
        {label}
      </span>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 14, color: highlight ? '#e8733a' : '#ddd7d0', fontWeight: highlight ? 600 : 400, lineHeight: 1.45 }}>
          {value ?? '—'}
        </span>
        {note && (
          <span style={{ fontSize: 12, color: '#4a4540', lineHeight: 1.55 }}>{note}</span>
        )}
        <SourceTag label={source} />
      </div>
    </div>
  )
}

function ConfidenceBar({ label, score, delay = 0 }: { label: string; score: number; delay?: number }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 9 }}>
        <span style={{ fontSize: 13, color: '#7a7068' }}>{label}</span>
        <span style={{ fontSize: 12, color: '#ddd7d0', fontFamily: "'JetBrains Mono', monospace" }}>
          {score} / 10
        </span>
      </div>
      <div style={{ height: 3, background: 'rgba(255,255,255,0.07)', borderRadius: 9999, overflow: 'hidden' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score * 10}%` }}
          transition={{ duration: 0.9, ease: 'easeOut', delay }}
          style={{ height: '100%', background: '#e8733a', borderRadius: 9999 }}
        />
      </div>
    </div>
  )
}

function SynthesisCard({ heading, body }: { heading: string; body: string }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.015)',
      border: '1px solid rgba(255,255,255,0.055)',
      borderRadius: 10, padding: '22px 24px',
    }}>
      <div style={{
        fontSize: 10, fontWeight: 700, letterSpacing: '0.13em',
        textTransform: 'uppercase', color: '#4a4540', marginBottom: 14,
      }}>
        {heading}
      </div>
      {body.split('\n').map((line, i) => {
        if (!line.trim()) return <div key={i} style={{ height: 5 }} />
        // Highlight source tags like (from OM), (from BCAD), etc.
        const parts = line.split(/(\(from [^)]+\)|\(calculated [^)]+\))/g)
        return (
          <p key={i} style={{ fontSize: 13, color: '#9e9087', lineHeight: 1.8, margin: 0 }}>
            {parts.map((p, j) =>
              p.startsWith('(from') || p.startsWith('(calculated') ? (
                <span key={j} style={{ color: 'rgba(232,115,58,0.55)', fontSize: 11 }}>{p}</span>
              ) : p
            )}
          </p>
        )
      })}
    </div>
  )
}

// ─── Data helpers ─────────────────────────────────────────────────────────────

function sd(state: AnalysisState, skill: string): Record<string, unknown> {
  return (state.skills[skill]?.data as Record<string, unknown>) ?? {}
}

function parseSections(text: string): { heading: string; body: string }[] {
  const out: { heading: string; body: string }[] = []
  let cur: { heading: string; lines: string[] } | null = null
  for (const line of text.split('\n')) {
    if (line.startsWith('## ')) {
      if (cur) out.push({ heading: cur.heading, body: cur.lines.join('\n').trim() })
      cur = { heading: line.slice(3).trim(), lines: [] }
    } else if (cur) {
      cur.lines.push(line)
    }
  }
  if (cur) out.push({ heading: cur.heading, body: cur.lines.join('\n').trim() })
  return out
}

function fmtM(n: unknown): string | null {
  const v = Number(n)
  if (!v || isNaN(v)) return null
  return v >= 1_000_000 ? `$${(v / 1_000_000).toFixed(1)}M` : `$${v.toLocaleString()}`
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function ResultsPanel({
  state, onBack, onExport,
}: {
  state: AnalysisState
  onBack: () => void
  onExport: () => void
}) {
  const verdict = state.verdict ?? 'UNKNOWN'
  const vc = VC[verdict] ?? VC.UNKNOWN

  const parse      = sd(state, 'parse_om')
  const owner      = sd(state, 'owner_lookup')
  const deed       = sd(state, 'deed_lookup')
  const tax        = sd(state, 'tax_lookup')
  const viols      = sd(state, 'violations_lookup')
  const comps      = sd(state, 'comps_lookup')
  const uw         = sd(state, 'underwrite')
  const mat        = sd(state, 'maturity_estimator')

  // Property
  const address    = String(parse.address ?? '')
  const city       = String(parse.city ?? '')
  const stAbbr     = String(parse.state ?? '')
  const units      = parse.units ? `${parse.units} units` : null
  const yearBuilt  = parse.year_built ? `Built ${parse.year_built}` : null
  const askPrice   = fmtM(parse.asking_price)

  // Owner
  const ownerName  = owner.owner_name ? String(owner.owner_name) : null
  const ownerSt    = owner.owner_state ? String(owner.owner_state) : null
  const oos        = Boolean(owner.out_of_state)
  const ownerVal   = ownerName
    ? [ownerName, oos ? `out-of-state (${ownerSt})` : null].filter(Boolean).join(' · ')
    : null

  // Deed
  const lender     = deed.lender ? String(deed.lender) : null
  const loanAmt    = fmtM(deed.loan_amount)
  const matDate    = deed.maturity_date ? String(deed.maturity_date) : null
  const debtVal    = [lender, loanAmt, matDate ? `matures ${matDate}` : null].filter(Boolean).join(' · ') || null

  // Maturity
  const monthsRem  = mat.months_remaining as number | undefined
  const pressure   = mat.pressure_level ? String(mat.pressure_level) : null
  const matVal     = monthsRem !== undefined
    ? monthsRem < 0
      ? `${Math.abs(monthsRem)} months past maturity — HIGH refi pressure`
      : `${monthsRem} months to maturity${pressure ? ` · ${pressure} pressure` : ''}`
    : null

  // Tax
  const taxDelinq  = Boolean(tax.delinquent)
  const taxDue     = fmtM(tax.total_due)
  const taxVal     = taxDelinq
    ? `Delinquent${taxDue ? ` · ${taxDue} owed` : ''}`
    : 'Current — no delinquencies'

  // Violations
  const violCount  = (viols.open_count as number | undefined) ?? 0
  const violVal    = violCount > 0 ? `${violCount} open violation${violCount !== 1 ? 's' : ''}` : 'No open violations'

  // Comps
  const market     = (comps.market as Record<string, unknown> | undefined) ?? {}
  const medRent    = market.median_rent ? `$${Number(market.median_rent).toLocaleString()}/mo median rent` : null
  const vacRate    = market.vacancy_pct != null ? `${market.vacancy_pct}% vacancy` : null
  const compsVal   = [medRent, vacRate].filter(Boolean).join(' · ') || null
  const compCount  = (comps.comp_count as number | undefined) ?? 0

  // Underwrite
  const noi        = fmtM(uw.noi_estimate)
  const capRate    = uw.cap_rate_at_ask ? `${(Number(uw.cap_rate_at_ask) * 100).toFixed(1)}% cap rate` : null
  const ppu        = fmtM(uw.price_per_unit)
  const uwVal      = [noi && `${noi} NOI`, capRate, ppu && `${ppu}/unit`].filter(Boolean).join(' · ') || null

  // Confidence scores
  const ownerScore = ownerName ? (oos ? 9 : 8) : 3
  const debtScore  = lender ? (monthsRem !== undefined && monthsRem < 12 ? 5 : 8) : 3
  const rentScore  = medRent ? 9 : compCount > 0 ? 6 : 3
  const permitScore = Object.keys(viols).length > 0 ? (violCount === 0 ? 9 : violCount <= 2 ? 6 : 4) : 3
  const compScore  = compCount >= 3 ? 9 : compCount > 0 ? 6 : 3

  // Synthesis
  const allSections = parseSections(state.synthesisText)
  const blSection   = allSections.find(s => s.heading.toLowerCase().includes('bottom-line') || s.heading.toLowerCase().includes('recommendation'))
  const reasoning   = blSection?.body.replace(/^(PURSUE|WATCHLIST|PASS)\s*/i, '').trim() ?? ''
  const detailSections = allSections.filter(s => !s.heading.toLowerCase().includes('bottom-line') && !s.heading.toLowerCase().includes('recommendation'))

  const subheader = [city && stAbbr ? `${city}, ${stAbbr}` : null, units, yearBuilt, askPrice && `Asking ${askPrice}`].filter(Boolean).join(' · ')

  return (
    <div style={{
      minHeight: '100vh', background: '#0f0e0d', color: '#e5e2e1',
      fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      overflowY: 'auto', WebkitFontSmoothing: 'antialiased',
    }}>

      {/* Header */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 36px', height: 62,
        background: 'rgba(15,14,13,0.92)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em', color: '#fff' }}>Nido & Key</span>
          <span style={{ width: 1, height: 14, background: 'rgba(255,255,255,0.1)' }} />
          <span style={{ fontSize: 12, color: 'rgba(200,196,192,0.4)', letterSpacing: '0.02em' }}>Analysis Report</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={onExport} style={{
            padding: '7px 20px', borderRadius: 9999,
            background: '#e8733a', color: '#fff', border: 'none',
            fontSize: 13, fontWeight: 600, cursor: 'pointer', letterSpacing: '0.01em',
          }}>
            Get the Full Memo
          </button>
          <button onClick={onBack} style={{
            padding: '7px 18px', borderRadius: 9999,
            background: 'rgba(255,255,255,0.06)', color: '#9e9087',
            border: '1px solid rgba(255,255,255,0.08)', fontSize: 13, fontWeight: 500, cursor: 'pointer',
          }}>
            New analysis
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 1120, margin: '0 auto', padding: '44px 36px 80px' }}>

        {/* ── Property hero ── */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}
          style={{ marginBottom: 44 }}>
          {subheader && (
            <div style={{ fontSize: 13, color: '#4a4540', marginBottom: 8, letterSpacing: '0.01em' }}>
              {subheader}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: 38, fontWeight: 700, letterSpacing: '-0.025em', color: '#fff', lineHeight: 1.12, margin: 0 }}>
              {address || 'Analysis Report'}
            </h1>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '7px 16px', borderRadius: 9999,
              background: vc.bg, border: `1.5px solid ${vc.border}`,
            }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: vc.color }} />
              <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', color: vc.color }}>
                {verdict}
              </span>
            </div>
          </div>
          {reasoning && (
            <p style={{ marginTop: 16, fontSize: 15, color: '#7a7068', lineHeight: 1.75, maxWidth: 780 }}>
              {reasoning}
            </p>
          )}
        </motion.div>

        {/* ── Two-column: data rows + confidence ── */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.1 }}
          style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 28, marginBottom: 52 }}
        >
          {/* Left: data rows */}
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.055)',
            borderRadius: 12, padding: '4px 28px 4px',
          }}>
            {ownerVal && (
              <DataRow label="Ownership" value={ownerVal} source="Bexar County Appraisal District"
                note={oos ? 'Out-of-state operator — absence adds exit motivation signal' : undefined}
                highlight={oos}
              />
            )}
            {debtVal && (
              <DataRow label="Debt" value={debtVal} source="Bexar County Clerk public records"
                note={monthsRem !== undefined && monthsRem < 12 ? 'Loan maturity approaching — refi pressure elevated' : undefined}
                highlight={monthsRem !== undefined && monthsRem < 6}
              />
            )}
            {matVal && (
              <DataRow label="Loan pressure" value={matVal} source="ATTOM origination date + calculated maturity estimate"
                highlight={monthsRem !== undefined && monthsRem < 0}
              />
            )}
            <DataRow label="Tax status" value={taxVal} source="Bexar County Appraisal District (BCAD)"
              highlight={taxDelinq}
            />
            {compsVal && (
              <DataRow label="Market rents" value={compsVal} source="U.S. Census ACS 5-year estimates"
                note="Submarket benchmark — compare against in-place rents to size value-add gap"
              />
            )}
            <DataRow label="Code violations" value={violVal} source="City of San Antonio Code Enforcement"
              highlight={violCount > 0}
            />
            {uwVal && (
              <DataRow label="Underwrite" value={uwVal} source="Calculated from OM in-place rents + Census benchmarks" />
            )}
            {askPrice && (
              <DataRow label="Asking price" value={askPrice} source="Offering memorandum" last />
            )}
          </div>

          {/* Right: confidence bars + data note */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div style={{
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.055)',
              borderRadius: 12, padding: '26px 26px',
              flex: 1,
            }}>
              <div style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
                textTransform: 'uppercase', color: '#4a4540', marginBottom: 24,
              }}>
                Signal Confidence
              </div>
              <ConfidenceBar label="Ownership clarity"  score={ownerScore}   delay={0.15} />
              <ConfidenceBar label="Debt health"         score={debtScore}    delay={0.25} />
              <ConfidenceBar label="Rent upside"         score={rentScore}    delay={0.35} />
              <ConfidenceBar label="Permit risk"         score={permitScore}  delay={0.45} />
              <ConfidenceBar label="Comp confidence"     score={compScore}    delay={0.55} />
            </div>

            <div style={{
              padding: '16px 20px',
              background: 'rgba(232,115,58,0.04)',
              border: '1px solid rgba(232,115,58,0.1)',
              borderRadius: 10,
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(232,115,58,0.45)', marginBottom: 8 }}>
                Data sources
              </div>
              <p style={{ fontSize: 12, color: '#4a4540', lineHeight: 1.7, margin: 0 }}>
                Bexar County Appraisal District, Bexar County Clerk, U.S. Census ACS, HUD SAFMR, City of San Antonio, and the offering memorandum. Loan maturity estimated from ATTOM origination data — actual terms may differ. Texas non-disclosure state.
              </p>
            </div>
          </div>
        </motion.div>

        {/* ── Full analysis sections ── */}
        {detailSections.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.2 }}
          >
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
              textTransform: 'uppercase', color: '#4a4540', marginBottom: 20,
            }}>
              Full Analysis
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {detailSections.map((s, i) => (
                <SynthesisCard key={i} heading={s.heading} body={s.body} />
              ))}
            </div>
          </motion.div>
        )}

        {/* Footer */}
        <div style={{
          marginTop: 56, paddingTop: 24,
          borderTop: '1px solid rgba(255,255,255,0.04)',
          fontSize: 11, color: '#2d2a27', lineHeight: 1.8,
        }}>
          Loan maturity figures are estimates derived from ATTOM origination dates. Texas is a non-disclosure state — recent sale prices are not available from public records. All figures retrieved {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}. Nido & Key — nidoandkey.com
        </div>
      </main>
    </div>
  )
}
