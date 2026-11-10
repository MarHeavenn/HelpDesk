import { strings } from '@/lib/strings'

const STATUS_STYLES: Record<string, string> = {
  Abierto: 'bg-sky-50 text-sky-700 ring-sky-200',
  'En progreso': 'bg-amber-50 text-amber-700 ring-amber-200',
  Resuelto: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  Cerrado: 'bg-slate-100 text-slate-600 ring-slate-200',
}

const PRIORITY_STYLES: Record<string, string> = {
  Crítica: 'bg-red-50 text-red-700 ring-red-200',
  Alta: 'bg-orange-50 text-orange-700 ring-orange-200',
  Media: 'bg-amber-50 text-amber-700 ring-amber-200',
  Baja: 'bg-slate-100 text-slate-600 ring-slate-200',
}

function badgeClass(styles: Record<string, string>, value: string): string {
  return styles[value] ?? 'bg-slate-100 text-slate-600 ring-slate-200'
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${badgeClass(
        STATUS_STYLES,
        status,
      )}`}
    >
      {status}
    </span>
  )
}

export function PriorityBadge({ priority }: { priority: string | null }) {
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${badgeClass(
        PRIORITY_STYLES,
        priority ?? '',
      )}`}
    >
      {priority ?? strings.dashboard.noPriority}
    </span>
  )
}
