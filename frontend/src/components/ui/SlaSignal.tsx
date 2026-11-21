import {
  CheckCircle2,
  Clock3,
  MinusCircle,
  XCircle,
  type LucideIcon,
} from 'lucide-react'

import { slaLevel, type SlaLevel } from '@/lib/sla'
import { strings } from '@/lib/strings'
import type { TicketSla } from '@/types/ticket'

const STYLES: Record<SlaLevel, string> = {
  normal: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  riesgo: 'bg-amber-50 text-amber-800 ring-amber-300',
  vencido: 'bg-red-50 text-red-700 ring-red-300',
  sin_sla: 'bg-slate-100 text-slate-500 ring-slate-200',
}

const ICONS: Record<SlaLevel, LucideIcon> = {
  normal: CheckCircle2,
  riesgo: Clock3,
  vencido: XCircle,
  sin_sla: MinusCircle,
}

function labelFor(sla: TicketSla | null, level: SlaLevel): string {
  if (level === 'normal' && sla) {
    const known = strings.tickets.slaStatus as Record<string, string>
    return known[sla.status] ?? strings.tickets.slaStatus.en_tiempo
  }
  const signal = strings.tickets.slaSignal as Record<string, string>
  return signal[level]
}

/** Señal de SLA reutilizable: color + texto + forma (RF-124, RF-131). */
export default function SlaSignal({ sla }: { sla: TicketSla | null }) {
  const level = slaLevel(sla)
  const Icon = ICONS[level]

  return (
    <span
      data-level={level}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${STYLES[level]}`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {labelFor(sla, level)}
    </span>
  )
}
