import { useEffect, useState } from 'react'

import { ApiError } from '@/api/httpClient'
import { type TicketsApi, ticketsApi } from '@/api/tickets.api'
import EmptyState from '@/components/ui/EmptyState'
import { PriorityBadge, StatusBadge } from '@/components/ui/Badges'
import ErrorState from '@/components/ui/ErrorState'
import PageHeader from '@/components/ui/PageHeader'
import Skeleton from '@/components/ui/Skeleton'
import { useAuth } from '@/context/AuthContext'
import { useMyTickets } from '@/hooks/useMyTickets'
import TicketDetailModal from '@/components/tickets/TicketDetailModal'
import { techniciansApi, type TechniciansApi } from '@/api/technicians.api'
import { formatTicketDate } from '@/lib/dates'
import { friendlyTicketId, mapTicket } from '@/lib/ticketMapper'
import { strings } from '@/lib/strings'

function TicketsSkeleton() {
  return (
    <div role="status" aria-label={strings.tickets.loading} className="space-y-3">
      {Array.from({ length: 4 }).map((_, index) => (
        <Skeleton key={index} className="h-14 w-full" />
      ))}
    </div>
  )
}

export default function MyTicketsPage({ api, directory }: { api?: TicketsApi; directory?: TechniciansApi }) {
  const { user, logout } = useAuth()
  const query = useMyTickets(user?.role ?? null, api ?? ticketsApi)
  const unauthorized = query.error instanceof ApiError && query.error.status === 401
  const isTechnician = user?.role === 'tecnico'
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null)

  useEffect(() => {
    if (unauthorized) void logout().catch(() => undefined)
  }, [logout, unauthorized])

  if (!user || unauthorized) return null

  const tickets = Array.isArray(query.data) ? query.data.map(mapTicket) : []
  const selectedTicket = tickets.find((item) => item.id === selectedTicketId)
  const emptyTitle = isTechnician
    ? strings.tickets.emptyAssignedTitle
    : strings.tickets.emptyTitle
  const emptyBody = isTechnician
    ? strings.tickets.emptyAssignedBody
    : strings.tickets.emptyBody

  return (
    <>
      <PageHeader
        title={strings.tickets.title}
        subtitle={isTechnician ? strings.tickets.assignedSubtitle : strings.tickets.subtitle}
        actions={
          <a
            href="/tickets/nuevo"
            className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
          >
            {strings.tickets.create}
          </a>
        }
      />

      {query.isPending ? <TicketsSkeleton /> : null}
      {query.isError && !unauthorized ? (
        <ErrorState
          title={strings.tickets.errorTitle}
          message={query.error instanceof Error ? query.error.message : strings.tickets.errorBody}
          retryLabel={strings.common.retry}
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.isSuccess && tickets.length === 0 ? (
        <EmptyState
          title={emptyTitle}
          message={emptyBody}
          action={
            <a
              href="/tickets/nuevo"
              className="inline-block rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
            >
              {strings.tickets.create}
            </a>
          }
        />
      ) : null}
      {tickets.length > 0 ? (
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <caption className="sr-only">{strings.tickets.title}</caption>
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-semibold">{strings.tickets.id}</th>
                  <th className="px-5 py-3 font-semibold">{strings.tickets.titleColumn}</th>
                  <th className="px-5 py-3 font-semibold">{strings.tickets.priority}</th>
                  <th className="px-5 py-3 font-semibold">{strings.tickets.status}</th>
                  <th className="px-5 py-3 font-semibold">{strings.tickets.assignee}</th>
                  <th className="px-5 py-3 font-semibold">{strings.tickets.createdAt}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tickets.map((ticket) => (
                  <tr key={ticket.id} className="align-middle hover:bg-slate-50">
                    <td className="whitespace-nowrap px-5 py-4 font-mono text-xs text-slate-500">
                      {friendlyTicketId(ticket.id)}
                    </td>
                    <td className="min-w-[16rem] px-5 py-4 font-medium text-slate-900">
                      {ticket.title}
                    </td>
                    <td className="whitespace-nowrap px-5 py-4">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="whitespace-nowrap px-5 py-4">
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                      {ticket.assignee?.name ?? strings.tickets.unassigned}
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-slate-500">
                      {formatTicketDate(ticket.createdAt)}
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-right">
                      <button type="button" onClick={() => setSelectedTicketId(ticket.id)} className="text-sm font-semibold text-primary hover:underline" aria-label={strings.tickets.viewDetail(ticket.displayId)}>
                        Ver detalle
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      {selectedTicket && user ? (
        <TicketDetailModal
          ticket={selectedTicket}
          role={user.role}
          api={api ?? ticketsApi}
          techniciansApi={directory ?? techniciansApi}
          onClose={() => setSelectedTicketId(null)}
          onUpdated={() => void query.refetch()}
        />
      ) : null}
    </>
  )
}
