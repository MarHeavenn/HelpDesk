import { PriorityBadge, StatusBadge } from '@/components/ui/Badges'
import { formatTicketDate } from '@/lib/dates'
import { friendlyTicketId } from '@/lib/format'
import { strings } from '@/lib/strings'
import type { TicketSla, TicketSummary } from '@/types/ticket'

const SLA_STYLES: Record<string, string> = {
  en_tiempo: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  en_riesgo: 'bg-amber-50 text-amber-700 ring-amber-200',
  cumplido: 'bg-sky-50 text-sky-700 ring-sky-200',
  incumplido: 'bg-red-50 text-red-700 ring-red-200',
}

function slaLabel(sla: TicketSla): string {
  const known = strings.tickets.slaStatus
  return (known as Record<string, string>)[sla.status] ?? sla.status
}

function SlaCell({ sla }: { sla: TicketSla | null }) {
  if (!sla) {
    return <span className="text-slate-400">{strings.tickets.noSla}</span>
  }
  return (
    <div className="space-y-0.5">
      <span
        className={`inline-flex whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${
          SLA_STYLES[sla.status] ?? 'bg-slate-100 text-slate-600 ring-slate-200'
        }`}
      >
        {slaLabel(sla)}
      </span>
      <p className="whitespace-nowrap text-xs text-slate-500">
        {strings.tickets.detail.due}: {formatTicketDate(sla.due_at)}
      </p>
    </div>
  )
}

/** Tabla compartida por «Todos los tickets» y «Mis tickets» (RF-119, RF-120). */
export default function TicketTable({
  tickets,
  caption,
  onOpen,
}: {
  tickets: readonly TicketSummary[]
  caption: string
  onOpen: (ticketId: string) => void
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-4 py-3 font-semibold">
              {strings.dashboard.ticketId}
            </th>
            <th scope="col" className="px-4 py-3 font-semibold">
              {strings.dashboard.ticketTitle}
            </th>
            <th scope="col" className="px-4 py-3 font-semibold">
              {strings.dashboard.priority}
            </th>
            <th scope="col" className="px-4 py-3 font-semibold">
              {strings.dashboard.status}
            </th>
            <th scope="col" className="px-4 py-3 font-semibold">
              {strings.dashboard.assignee}
            </th>
            <th scope="col" className="px-4 py-3 font-semibold">
              {strings.tickets.sla}
            </th>
            <th scope="col" className="px-4 py-3 font-semibold">
              {strings.dashboard.createdAt}
            </th>
            <th scope="col" className="px-4 py-3 font-semibold">
              <span className="sr-only">{strings.dashboard.viewAll}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tickets.map((ticket) => (
            <tr key={ticket.id} className="align-middle hover:bg-slate-50">
              <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-500">
                {friendlyTicketId(ticket.id)}
              </td>
              <td className="min-w-[12rem] px-4 py-3 font-medium text-slate-900">
                {ticket.title}
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                <PriorityBadge priority={ticket.priority} />
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                <StatusBadge status={ticket.status} />
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                {ticket.assignee?.name ?? strings.tickets.unassigned}
              </td>
              <td className="px-4 py-3">
                <SlaCell sla={ticket.sla} />
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                {formatTicketDate(ticket.created_at)}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={() => onOpen(ticket.id)}
                  aria-label={strings.tickets.viewDetailLabel(
                    friendlyTicketId(ticket.id),
                  )}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  {strings.tickets.viewDetail}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
