import { motion, AnimatePresence } from 'framer-motion'
import { Loader2, Check, AlertCircle } from 'lucide-react'
import type { SkillState } from '../types'

// Label color per skill
const LABEL_COLORS: Record<string, { bg: string; text: string }> = {
  parse_om:           { bg: '#7C3AED', text: '#fff' },
  owner_lookup:       { bg: '#0F766E', text: '#fff' },
  deed_lookup:        { bg: '#1D4ED8', text: '#fff' },
  portfolio_crawler:  { bg: '#6D28D9', text: '#fff' },
  permit_lookup:      { bg: '#B45309', text: '#fff' },
  tax_lookup:         { bg: '#047857', text: '#fff' },
  violations_lookup:  { bg: '#DC2626', text: '#fff' },
  comps_lookup:       { bg: '#0369A1', text: '#fff' },
  maturity_estimator: { bg: '#9333EA', text: '#fff' },
  synthesize_analysis:{ bg: '#1a1916', text: '#fff' },
}

function Flag({ text, type }: { text: string; type: 'warn' | 'ok' }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
      background: type === 'warn' ? 'var(--red-bg)' : 'var(--green-bg)',
      color: type === 'warn' ? 'var(--red)' : 'var(--green)',
    }}>
      {type === 'warn' ? '⚠ ' : '✓ '}{text}
    </span>
  )
}

function DataRow({ k, v, flag }: { k: string; v: string; flag?: { text: string; type: 'warn' | 'ok' } }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '3px 0' }}>
      <span style={{ fontSize: 12, color: 'var(--text-3)', minWidth: 110, flexShrink: 0 }}>{k}</span>
      <span style={{ fontSize: 12, color: 'var(--text-2)', fontFamily: 'monospace', flex: 1 }}>{v}</span>
      {flag && <Flag text={flag.text} type={flag.type} />}
    </div>
  )
}

function SkillData({ name, data }: { name: string; data: Record<string, unknown> }) {
  if (name === 'parse_om') return (
    <>
      <DataRow k="Asset class" v={String(data.asset_class ?? '—')} />
      <DataRow k="Property type" v={String(data.property_type ?? '—')} />
      {data.year_built && <DataRow k="Year built" v={String(data.year_built)} />}
    </>
  )
  if (name === 'owner_lookup') {
    const oos = data.out_of_state as boolean | undefined
    return (
      <>
        <DataRow k="Owner" v={String(data.owner_name ?? '—')} />
        <DataRow k="Address" v={String(data.owner_address ?? '—')} />
        {oos && <DataRow k="Owner state" v={String(data.owner_state)} flag={{ text: `Out-of-state (${data.owner_state})`, type: 'warn' }} />}
      </>
    )
  }
  if (name === 'deed_lookup') {
    const maturity = data.maturity_date as string | undefined
    return (
      <>
        <DataRow k="Lender" v={String(data.lender ?? '—')} />
        <DataRow k="Loan amount" v={data.loan_amount ? `$${Number(data.loan_amount).toLocaleString()}` : '—'} />
        <DataRow k="Originated" v={String(data.origination_date ?? '—')} />
        <DataRow k="Maturity" v={maturity || 'N/A'} />
        <DataRow k="Last sale" v={data.last_sale_price ? `$${Number(data.last_sale_price).toLocaleString()}` : '—'} />
        <DataRow k="Appraised" v={data.appraised_value ? `$${Number(data.appraised_value).toLocaleString()}` : '—'} />
      </>
    )
  }
  if (name === 'tax_lookup') {
    const delinquent = data.delinquent as boolean | undefined
    return (
      <>
        <DataRow k="Status" v={String(data.status ?? '—')}
          flag={delinquent ? { text: `${data.total_due ?? 'Amount unknown'} owed`, type: 'warn' } : { text: 'Current', type: 'ok' }} />
        {data.tax_year && <DataRow k="Tax year" v={String(data.tax_year)} />}
        {data.total_due && <DataRow k="Total due" v={String(data.total_due)} />}
      </>
    )
  }
  if (name === 'violations_lookup') {
    const open = (data.open_count as number) ?? 0
    const total = (data.count as number) ?? 0
    return (
      <>
        <DataRow k="Open violations" v={String(open)}
          flag={open > 0 ? { text: `${open} open`, type: 'warn' } : { text: 'None open', type: 'ok' }} />
        <DataRow k="Total on record" v={String(total)} />
      </>
    )
  }
  if (name === 'comps_lookup') {
    const market = data.market as Record<string, unknown> | undefined
    const comps = data.comps as Array<unknown> | undefined
    return (
      <>
        <DataRow k="Comps found" v={String(data.comp_count ?? comps?.length ?? '0')} />
        <DataRow k="Median rent" v={market?.median_rent ? `$${Number(market.median_rent).toLocaleString()}/mo` : '—'} />
        <DataRow k="Vacancy" v={market?.vacancy_pct != null ? `${market.vacancy_pct}%` : '—'} />
        <DataRow k="Renter %" v={market?.renter_pct != null ? `${market.renter_pct}%` : '—'} />
      </>
    )
  }
  if (name === 'portfolio_crawler') {
    const props = data.properties as Array<unknown> | undefined
    return (
      <>
        <DataRow k="Properties found" v={String(data.property_count ?? props?.length ?? '0')} />
        <DataRow k="Owner" v={String(data.owner_name ?? '—')} />
      </>
    )
  }
  if (name === 'maturity_estimator') {
    const months = data.months_remaining as number | undefined
    const pressure = String(data.pressure_level ?? '')
    const pastDue = months !== undefined && months < 0
    return (
      <>
        <DataRow k="Months remaining" v={pastDue ? `${Math.abs(months!)} mo PAST DUE` : `${months ?? '—'} mo`}
          flag={pastDue ? { text: 'High refi pressure', type: 'warn' } : undefined} />
        <DataRow k="Pressure level" v={pressure.toUpperCase()} />
        {data.interpretation && <DataRow k="Signal" v={String(data.interpretation)} />}
      </>
    )
  }
  if (name === 'permit_lookup') {
    const permits = data.permits as Array<unknown> | undefined
    return <DataRow k="Permits on file" v={String(data.count ?? permits?.length ?? '0')} />
  }
  if (name === 'synthesize_analysis') {
    return <DataRow k="Status" v={data.ready ? 'Research complete — writing analysis' : '—'} />
  }
  return null
}

function SourceTag({ source }: { source: string }) {
  return (
    <div style={{
      fontSize: 10, color: 'var(--text-3)', marginTop: 8,
      paddingTop: 6, borderTop: '1px solid var(--border)',
      letterSpacing: '0.03em',
    }}>
      via {source}
    </div>
  )
}

function SkillCard({ skill }: { skill: SkillState }) {
  const lc = LABEL_COLORS[skill.name] ?? { bg: '#666', text: '#fff' }
  const isActive = skill.status === 'running' || skill.status === 'complete'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: isActive ? 1 : 0.35, y: 0, scale: 1 }}
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        overflow: 'hidden',
        transition: 'border-color 0.2s',
        borderColor: skill.status === 'running' ? 'rgba(124,58,237,0.3)' : 'var(--border)',
      }}
    >
      {/* Card header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px',
        borderBottom: skill.status === 'complete' && skill.data ? '1px solid var(--border)' : 'none',
      }}>
        <span style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '0.04em',
          padding: '3px 8px', borderRadius: 5,
          background: lc.bg, color: lc.text,
        }}>
          {skill.label}
        </span>
        <span style={{ display: 'flex', alignItems: 'center' }}>
          {skill.status === 'idle'     && <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--border-2)' }} />}
          {skill.status === 'running'  && <Loader2 size={14} color="var(--accent)" style={{ animation: 'spin 1s linear infinite' }} />}
          {skill.status === 'complete' && <Check size={14} color="var(--green)" />}
          {skill.status === 'error'    && <AlertCircle size={14} color="var(--red)" />}
        </span>
      </div>

      {/* Card data */}
      <AnimatePresence>
        {skill.status === 'complete' && skill.data && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 2 }}>
            <SkillData name={skill.name} data={skill.data} />
            {typeof skill.data.source === 'string' && skill.data.source && <SourceTag source={skill.data.source} />}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export function DataFeed({ skills, isAnalyzing: _isAnalyzing }: { skills: SkillState[]; isAnalyzing: boolean }) {
  return (
    <div>
      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}>
        Investigation
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <AnimatePresence initial={false}>
          {skills.map(skill => <SkillCard key={skill.name} skill={skill} />)}
        </AnimatePresence>
      </div>
    </div>
  )
}
