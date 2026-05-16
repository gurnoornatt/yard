import { MapPin, Home, DollarSign } from 'lucide-react'
import type { Verdict } from '../types'

const verdictColors: Record<string, string> = {
  PURSUE:    'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  WATCHLIST: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  PASS:      'bg-red-500/10 text-red-400 border-red-500/20',
}

function fmt(n: unknown) {
  if (typeof n !== 'number') return String(n ?? '—')
  return n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(2)}M` :
         n >= 1_000 ? `$${(n / 1_000).toFixed(0)}k` : String(n)
}

export function PropertyHeader({ data, verdict }: { data: Record<string, unknown>; verdict: Verdict | null }) {
  return (
    <div className="border-b border-white/5 px-6 py-4 flex items-start justify-between gap-4 shrink-0">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-white/40 text-xs mb-1">
          <MapPin size={11} />
          <span className="font-mono truncate">{String(data.address ?? '—')}</span>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-1.5 text-white/70 text-sm">
            <Home size={13} className="text-white/30" />
            <span>{String(data.units ?? '—')} units</span>
            <span className="text-white/20">·</span>
            <span>{String(data.year_built ?? '—')}</span>
            <span className="text-white/20">·</span>
            <span>{String(data.asset_class ?? '—')}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <div className="text-right">
          <div className="flex items-center gap-1 text-white text-base font-semibold">
            <DollarSign size={14} className="text-white/40" />
            {fmt(data.asking_price)}
          </div>
          <div className="text-white/30 text-xs">{fmt(data.price_per_unit)}/unit</div>
        </div>
        {verdict && (
          <span className={`text-xs font-semibold px-3 py-1.5 rounded-full border ${verdictColors[verdict] ?? 'bg-white/5 text-white/50 border-white/10'}`}>
            {verdict}
          </span>
        )}
      </div>
    </div>
  )
}
