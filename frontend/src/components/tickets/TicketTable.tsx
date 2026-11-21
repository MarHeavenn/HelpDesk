import { PriorityBadge, StatusBadge } from '@/components/ui/Badges'
import SlaSignal from '@/components/ui/SlaSignal'
import { formatTicketDate } from '@/lib/dates'
import { friendlyTicketId } from '@/lib/format'
import { strings } from '@/lib/strings'
import type { TicketSummary } from '@/types/ticket'

function SlaCell({ sla }: { sla: TicketSummary['sla'] }) {
  return (
    <div className="space-y-0.5">
      <SlaSignal sla={sla} />
      {sla ? (
        <p className="whitespace-nowrap text-xs text-slate-500">
          {strings.tickets.detail.due}: {formatTicketDate(sla.due_at)}
        </p>
      ) : null}
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
