import { Link } from 'react-router-dom'

import { PriorityBadge, StatusBadge } from '@/components/ui/Badges'
import { formatTicketDate } from '@/lib/dates'
import { friendlyTicketId } from '@/lib/format'
import { strings } from '@/lib/strings'
import type { RecentTicket } from '@/types/dashboard'

/** Tabla con los cinco tickets más recientes (RF-88, RF-91). */
export default function RecentTicketsTable({
  tickets,
}: {
  tickets: RecentTicket[]
}) {
  return (
    <section
      aria-label={strings.dashboard.recent}
      className="rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-900">
          {strings.dashboard.recent}
        </h2>
        <Link
          to="/tickets"
          className="text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          {strings.dashboard.viewAll}
        </Link>
      </header>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <caption className="sr-only">{strings.dashboard.recent}</caption>
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" className="px-5 py-3 font-semibold">
                {strings.dashboard.ticketId}
              </th>
              <th scope="col" className="px-5 py-3 font-semibold">
                {strings.dashboard.ticketTitle}
              </th>
              <th scope="col" className="px-5 py-3 font-semibold">
                {strings.dashboard.priority}
              </th>
              <th scope="col" className="px-5 py-3 font-semibold">
                {strings.dashboard.status}
              </th>
              <th scope="col" className="px-5 py-3 font-semibold">
                {strings.dashboard.assignee}
              </th>
              <th scope="col" className="px-5 py-3 font-semibold">
                {strings.dashboard.createdAt}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {tickets.map((ticket) => (
              <tr key={ticket.id} className="align-middle">
                <td className="whitespace-nowrap px-5 py-3 font-mono text-xs text-slate-500">
                  {friendlyTicketId(ticket.id)}
                </td>
                <td className="min-w-[12rem] px-5 py-3 font-medium text-slate-900">
                  {ticket.title}
                </td>
                <td className="whitespace-nowrap px-5 py-3">
                  <PriorityBadge priority={ticket.priority} />
                </td>
                <td className="whitespace-nowrap px-5 py-3">
                  <StatusBadge status={ticket.status} />
                </td>
                <td className="whitespace-nowrap px-5 py-3 text-slate-600">
                  {ticket.assignee?.name ?? strings.dashboard.unassigned}
                </td>
                <td className="whitespace-nowrap px-5 py-3 text-slate-500">
                  {formatTicketDate(ticket.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
