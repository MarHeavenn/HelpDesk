import { useEffect } from 'react'
import { Link } from 'react-router-dom'

import type { DashboardApi } from '@/api/dashboard.api'
import { ApiError } from '@/api/httpClient'
import { PriorityBadge, StatusBadge } from '@/components/ui/Badges'
import ErrorState from '@/components/ui/ErrorState'
import Skeleton from '@/components/ui/Skeleton'
import SlaSignal from '@/components/ui/SlaSignal'
import { useAuth } from '@/context/AuthContext'
import { useAttentionAlerts } from '@/hooks/useDashboard'
import { formatTicketDate } from '@/lib/dates'
import { friendlyTicketId } from '@/lib/format'
import { strings } from '@/lib/strings'
import type { TicketSummary } from '@/types/ticket'

const LINK_CLASS =
  'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40'

/** Barra proporcional del resumen; decorativa, el conteo va en texto (RF-129). */
function SummaryRow({
  label,
  count,
  total,
  barClass,
}: {
  label: string
  count: number
  total: number
  barClass: string
}) {
  const width = total > 0 ? (count / total) * 100 : 0

  return (
    <li className="rounded-lg bg-slate-50 px-3 py-2">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="font-semibold text-slate-900">{count}</span>
      </div>
      <div
        aria-hidden="true"
        className="mt-1 h-2 overflow-hidden rounded-full bg-slate-200"
      >
        <div className={`h-full rounded-full ${barClass}`} style={{ width: `${width}%` }} />
      </div>
    </li>
  )
}

function AlertRow({ ticket }: { ticket: TicketSummary }) {
  const breached = ticket.sla?.breached ?? false

  return (
    <li className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-slate-500">
            {friendlyTicketId(ticket.id)}
          </span>
          <span className="font-medium text-slate-900">{ticket.title}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PriorityBadge priority={ticket.priority} />
          <StatusBadge status={ticket.status} />
          <SlaSignal sla={ticket.sla ?? null} />
          <span className="text-xs text-slate-500">
            {ticket.assignee?.name ?? strings.dashboard.unassigned}
          </span>
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <span className="text-xs text-slate-500">
          {breached && ticket.sla
            ? `${strings.tickets.detail.due}: ${formatTicketDate(ticket.sla.due_at)}`
            : ticket.sla
              ? strings.dashboard.alerts.remaining(ticket.sla.remaining_minutes)
              : ''}
        </span>
        <Link
          to={`/tickets?q=${encodeURIComponent(ticket.id)}`}
          className={LINK_CLASS}
          aria-label={strings.dashboard.alerts.viewDetailLabel(
            friendlyTicketId(ticket.id),
          )}
        >
          {strings.tickets.viewDetail}
        </Link>
      </div>
    </li>
  )
}

/** Panel de alertas derivado de `GET /api/tickets/requiring-attention` (RF-126). */
export default function AlertsPanel({ api }: { api?: DashboardApi }) {
  const { user, logout } = useAuth()
  const isStaff =
    user?.role === 'administrador' || user?.role === 'tecnico'
  const query = useAttentionAlerts(api, isStaff)
  const alerts = query.data

  const unauthorized =
    query.error instanceof ApiError && query.error.status === 401

  useEffect(() => {
    if (!unauthorized) return
    void logout().catch(() => undefined)
  }, [logout, unauthorized])

  if (!isStaff || unauthorized) return null

  const nearDue =
    alerts?.filter((item) => item.sla?.near_due && !item.sla.breached).length ?? 0
  const breached = alerts?.filter((item) => item.sla?.breached).length ?? 0
  const total = nearDue + breached

  return (
    <section
      aria-label={strings.dashboard.alerts.title}
      className="rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="border-b border-slate-100 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-900">
          {strings.dashboard.alerts.title}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {strings.dashboard.alerts.subtitle}
        </p>
      </header>

      <div className="space-y-4 p-5">
        {query.isPending ? (
          <div
            role="status"
            aria-label={strings.dashboard.alerts.loading}
            className="space-y-3"
          >
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : null}

        {query.isError && !unauthorized ? (
          <ErrorState
            title={strings.dashboard.alerts.errorTitle}
            message={strings.dashboard.alerts.errorBody}
            retryLabel={strings.common.retry}
            onRetry={() => void query.refetch()}
          />
        ) : null}

        {alerts && total > 0 ? (
          <ul
            aria-label={strings.dashboard.alerts.summaryLabel}
            className="grid gap-3 sm:grid-cols-2"
          >
            <SummaryRow
              label={strings.dashboard.alerts.nearDue}
              count={nearDue}
              total={total}
              barClass="bg-amber-500"
            />
            <SummaryRow
              label={strings.dashboard.alerts.breached}
              count={breached}
              total={total}
              barClass="bg-red-500"
            />
          </ul>
        ) : null}

        {alerts?.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
            <p className="text-base font-semibold text-slate-900">
              {strings.dashboard.alerts.emptyTitle}
            </p>
            <p className="mx-auto mt-1 max-w-md text-sm text-slate-600">
              {strings.dashboard.alerts.emptyBody}
            </p>
          </div>
        ) : null}

        {alerts && alerts.length > 0 ? (
          <ul
            aria-label={strings.dashboard.alerts.listLabel}
            className="divide-y divide-slate-100 rounded-xl border border-slate-200"
          >
            {alerts.map((ticket) => (
              <AlertRow key={ticket.id} ticket={ticket} />
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  )
}
