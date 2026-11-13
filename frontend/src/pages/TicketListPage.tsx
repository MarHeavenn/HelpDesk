import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/httpClient'
import { ticketsApi, type TicketsApi } from '@/api/tickets.api'
import TicketDetailModal from '@/components/tickets/TicketDetailModal'
import TicketFilters from '@/components/tickets/TicketFilters'
import TicketTable from '@/components/tickets/TicketTable'
import EmptyState from '@/components/ui/EmptyState'
import ErrorState from '@/components/ui/ErrorState'
import Pagination from '@/components/ui/Pagination'
import Skeleton from '@/components/ui/Skeleton'
import { useAuth } from '@/context/AuthContext'
import { useTicketList } from '@/hooks/useTickets'
import {
  filterTickets,
  paginateTickets,
  parseTicketQuery,
  sortTickets,
  technicianOptions,
  ticketQueryToParams,
  type TicketFilters as Filters,
  type TicketListScope,
} from '@/lib/tickets'
import { strings } from '@/lib/strings'

const SKELETON_ROWS = 6

function TableSkeleton() {
  return (
    <div
      role="status"
      aria-label={strings.tickets.loading}
      className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      {Array.from({ length: SKELETON_ROWS }, (_, index) => (
        <Skeleton key={index} className="h-8 w-full" />
      ))}
    </div>
  )
}

/**
 * Listado compartido por «Todos los tickets» y «Mis tickets» (HU-23,
 * RF-119 a RF-121): filtros, orden y paginación en cliente con la query
 * string como fuente de verdad.
 */
export default function TicketListPage({
  scope,
  api = ticketsApi,
}: {
  scope: TicketListScope
  api?: TicketsApi
}) {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [openTicketId, setOpenTicketId] = useState<string | null>(null)

  const filters = useMemo(() => parseTicketQuery(searchParams), [searchParams])
  const listQuery = useTicketList(scope, api)
  const tickets = useMemo(() => listQuery.data ?? [], [listQuery.data])

  const technicians = useMemo(() => technicianOptions(tickets), [tickets])
  const filtered = useMemo(
    () => filterTickets(tickets, filters),
    [tickets, filters],
  )
  const sorted = useMemo(
    () => sortTickets(filtered, filters.sort),
    [filtered, filters.sort],
  )
  const page = useMemo(
    () => paginateTickets(sorted, filters.page),
    [sorted, filters.page],
  )

  const role = user?.role
  const showTechnician = role === 'administrador' || role === 'tecnico'

  // Una página fuera de rango se normaliza y se refleja en la URL.
  useEffect(() => {
    if (!listQuery.isSuccess) return
    if (filters.page !== page.page) {
      setSearchParams(ticketQueryToParams({ ...filters, page: page.page }), {
        replace: true,
      })
    }
  }, [listQuery.isSuccess, filters, page.page, setSearchParams])

  function changeFilters(next: Filters) {
    setSearchParams(ticketQueryToParams(next), { replace: true })
  }

  const unauthorized =
    listQuery.error instanceof ApiError && listQuery.error.status === 401

  if (unauthorized) return null

  return (
    <>
      {listQuery.isError && !unauthorized ? (
        <ErrorState
          title={strings.tickets.errorTitle}
          message={strings.tickets.errorBody}
          retryLabel={strings.common.retry}
          onRetry={() => void listQuery.refetch()}
        />
      ) : (
        <div className="space-y-4">
          <TicketFilters
            filters={filters}
            onChange={changeFilters}
            technicians={technicians}
            showTechnician={showTechnician}
          />

          {listQuery.isPending ? (
            <TableSkeleton />
          ) : tickets.length === 0 ? (
            <EmptyState
              title={strings.tickets.emptyTitle}
              message={strings.tickets.emptyBody}
              action={
                <Link
                  to="/tickets/nuevo"
                  className="inline-block rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
                >
                  {strings.tickets.emptyAction}
                </Link>
              }
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              title={strings.tickets.emptyFilteredTitle}
              message={strings.tickets.emptyFilteredBody}
              action={
                <button
                  type="button"
                  onClick={() =>
                    changeFilters({
                      ...filters,
                      query: '',
                      priority: 'all',
                      status: 'all',
                      assignee: 'all',
                      page: 1,
                    })
                  }
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  {strings.tickets.clear}
                </button>
              }
            />
          ) : (
            <>
              <p
                role="status"
                aria-live="polite"
                className="text-sm text-slate-600"
              >
                {strings.tickets.showing(page.from, page.to, page.total)}
              </p>
              <TicketTable
                tickets={page.items}
                caption={
                  scope === 'all'
                    ? strings.tickets.tableCaptionAll
                    : strings.tickets.tableCaptionMine
                }
                onOpen={setOpenTicketId}
              />
              <Pagination
                page={page.page}
                pages={page.pages}
                onChange={(next) =>
                  changeFilters({ ...filters, page: next })
                }
              />
            </>
          )}
        </div>
      )}

      <TicketDetailModal
        ticketId={openTicketId}
        onClose={() => setOpenTicketId(null)}
        api={api}
      />
    </>
  )
}
