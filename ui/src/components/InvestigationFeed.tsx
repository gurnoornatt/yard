import { motion, AnimatePresence } from 'framer-motion'
import { Check, Loader2, AlertCircle, Clock } from 'lucide-react'
import type { SkillState } from '../types'

const SKILL_ICONS: Record<string, string> = {
  parse_om:           '📄',
  owner_lookup:       '🏢',
  deed_lookup:        '📋',
  portfolio_crawler:  '🗺️',
  permit_lookup:      '🔨',
  tax_lookup:         '🏛️',
  violations_lookup:  '⚠️',
  comps_lookup:       '📊',
  maturity_estimator: '⏳',
  synthesize_analysis:'🧠',
}

function SkillCard({ skill }: { skill: SkillState }) {
  const icon = SKILL_ICONS[skill.name] ?? '•'
  const data = skill.data

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-xl border p-4 transition-colors ${
        skill.status === 'running'  ? 'border-white/10 bg-white/[0.03]' :
        skill.status === 'complete' ? 'border-white/8 bg-white/[0.02]' :
        skill.status === 'error'    ? 'border-red-500/20 bg-red-500/5' :
                                      'border-white/5 bg-transparent'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="text-base leading-none">{icon}</span>
          <span className={`text-sm font-medium ${skill.status === 'idle' ? 'text-white/25' : 'text-white/80'}`}>
            {skill.label}
          </span>
        </div>
        <div className="shrink-0 mt-0.5">
          {skill.status === 'idle'     && <Clock size={14} className="text-white/15" />}
          {skill.status === 'running'  && <Loader2 size={14} className="text-white/50 animate-spin" />}
          {skill.status === 'complete' && <Check size={14} className="text-emerald-400" />}
          {skill.status === 'error'    && <AlertCircle size={14} className="text-red-400" />}
        </div>
      </div>

      <AnimatePresence>
        {skill.status === 'complete' && data && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mt-3 overflow-hidden">
            <DataSummary name={skill.name} data={data} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function DataSummary({ name, data }: { name: string; data: Record<string, unknown> }) {
  if (name === 'parse_om') {
    return <Row label="Broker" value={String(data.broker ?? '—')} />
  }
  if (name === 'owner_lookup') {
    const hold = data.hold_period_years as number | undefined
    const outOfState = data.owner_state && data.owner_state !== 'TX'
    return (
      <div className="space-y-1">
        <Row label="Entity" value={String(data.llc_name ?? '—')} />
        <Row label="Principal" value={String(data.principal ?? '—')} />
        <Row label="Hold" value={hold ? `${hold} yrs` : '—'} flag={hold !== undefined && hold > 8 ? 'Tired landlord signal' : undefined} />
        {outOfState && <Flag text={`Out-of-state owner (${data.owner_state})`} />}
      </div>
    )
  }
  if (name === 'deed_lookup') {
    const loans = data.loans as Array<Record<string, unknown>> | undefined
    const loan = loans?.[0]
    if (!loan) return <Row label="Loans" value="None recorded" />
    const past = loan.note && String(loan.note).includes('past due')
    return (
      <div className="space-y-1">
        <Row label="Lender" value={String(loan.lender ?? '—')} />
        <Row label="Amount" value={loan.loan_amount ? `$${Number(loan.loan_amount).toLocaleString()}` : '—'} />
        <Row label="Maturity" value={String(loan.estimated_maturity ?? '—')} flag={past ? 'PAST DUE — forced seller signal' : undefined} flagColor="red" />
        <Row label="Type" value={loan.is_cmbs ? 'CMBS' : String(loan.lender_type ?? '—')} />
      </div>
    )
  }
  if (name === 'tax_lookup') {
    const delinquent = data.delinquent as boolean | undefined
    return (
      <div className="space-y-1">
        <Row label="Status" value={String(data.status ?? '—')} flag={delinquent ? `$${Number(data.delinquency_amount).toLocaleString()} owed — ${data.delinquency_years} yrs` : undefined} flagColor="red" />
        <Row label="Appraised" value={data.appraised_value ? `$${Number(data.appraised_value).toLocaleString()}` : '—'} />
      </div>
    )
  }
  if (name === 'violations_lookup') {
    const open = data.open_violations as number | undefined
    const total = data.total_violations as number | undefined
    if (!total) return <Row label="Violations" value="None recorded" />
    return (
      <div className="space-y-1">
        <Row label="Open" value={String(open ?? 0)} flag={open ? `${open} open violation${open > 1 ? 's' : ''}` : undefined} flagColor="red" />
        <Row label="Total" value={String(total ?? 0)} />
      </div>
    )
  }
  if (name === 'comps_lookup') {
    const avg = data.avg_price_per_unit as number | undefined
    const comps = data.comps as Array<Record<string, unknown>> | undefined
    return (
      <div className="space-y-1">
        <Row label="Submarket avg" value={avg ? `$${Number(avg).toLocaleString()}/unit` : '—'} />
        <Row label="Comps" value={comps ? `${comps.length} transactions` : '—'} />
        <Row label="Vacancy" value={data.submarket_vacancy ? `${(Number(data.submarket_vacancy) * 100).toFixed(0)}%` : '—'} />
      </div>
    )
  }
  if (name === 'portfolio_crawler') {
    const others = data.other_properties as Array<unknown> | undefined
    return (
      <div className="space-y-1">
        <Row label="Other props" value={others ? String(others.length) : '0'} />
        <Row label="Total units" value={String(data.total_units_in_portfolio ?? '—')} />
      </div>
    )
  }
  if (name === 'maturity_estimator') {
    const months = data.months_to_maturity as number | undefined
    const pressure = String(data.refi_pressure ?? '')
    return (
      <div className="space-y-1">
        <Row label="Pressure" value={pressure.toUpperCase()} flag={pressure === 'high' ? String(data.note ?? '') : undefined} flagColor="red" />
        <Row label="Months to maturity" value={months !== undefined ? (months < 0 ? `${Math.abs(months)} mo PAST DUE` : `${months} mo`) : '—'} />
      </div>
    )
  }
  return null
}

function Row({ label, value, flag, flagColor = 'amber' }: {
  label: string; value: string; flag?: string; flagColor?: 'red' | 'amber'
}) {
  return (
    <div className="flex items-start gap-2 text-xs">
      <span className="text-white/25 shrink-0 w-24">{label}</span>
      <span className="text-white/60 font-mono">{value}</span>
      {flag && (
        <span className={`ml-1 text-[10px] font-medium px-1.5 py-0.5 rounded ${
          flagColor === 'red' ? 'bg-red-500/15 text-red-400' : 'bg-amber-500/15 text-amber-400'
        }`}>{flag}</span>
      )}
    </div>
  )
}

function Flag({ text }: { text: string }) {
  return (
    <div className="mt-1 text-[10px] font-medium px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/15 inline-block">
      {text}
    </div>
  )
}

export function InvestigationFeed({ skills, isAnalyzing }: { skills: SkillState[]; isAnalyzing: boolean }) {
  const visible = skills.filter(s => s.status !== 'idle' || isAnalyzing)

  return (
    <div className="space-y-2">
      <p className="text-white/20 text-xs font-mono uppercase tracking-widest mb-4">Investigation</p>
      <AnimatePresence initial={false}>
        {skills.map(skill => (
          <SkillCard key={skill.name} skill={skill} />
        ))}
      </AnimatePresence>
      {!isAnalyzing && visible.length === 0 && (
        <p className="text-white/20 text-sm text-center py-8">Upload an OM to begin</p>
      )}
    </div>
  )
}
