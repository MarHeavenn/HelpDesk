import { useEffect } from 'react'
import { Link } from 'react-router-dom'

import AssigneeCard from '@/components/dashboard/AssigneeCard'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton'
import DistributionCard from '@/components/dashboard/DistributionCard'
import KpiCard from '@/components/dashboard/KpiCard'
import RecentTicketsTable from '@/components/dashboard/RecentTicketsTable'
import SlaCompliancePanel from '@/components/dashboard/SlaCompliancePanel'
import EmptyState from '@/components/ui/EmptyState'
import ErrorState from '@/components/ui/ErrorState'
import PageHeader from '@/components/ui/PageHeader'
import type { DashboardApi } from '@/api/dashboard.api'
import { ApiError } from '@/api/httpClient'
import { useAuth } from '@/context/AuthContext'
import { useTicketsDashboard } from '@/hooks/useDashboard'
import { formatLongDate, greetingForHour } from '@/lib/dates'
import { strings } from '@/lib/strings'

/** Dashboard real de tickets y SLA en `/` (RF-91, RF-92, RF-102). */
export default function DashboardPage({ api }: { api?: DashboardApi }) {
  const { user, logout } = useAuth()
  const query = useTicketsDashboard(api)
  const dashboard = query.data

  const unauthorized =
    query.error instanceof ApiError && query.error.status === 401

  useEffect(() => {
    if (!unauthorized) return
    void logout().catch(() => undefined)
  }, [logout, unauthorized])

  if (unauthorized) return null

  const now = new Date()
  const subtitle = user
    ? `${greetingForHour(now)}, ${user.name} · ${formatLongDate(now)}`
    : strings.dashboard.subtitle

  return (
    <>
      <PageHeader
        title={strings.dashboard.title}
        subtitle={subtitle}
        actions={
          <Link
            to="/tickets/nuevo"
            className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
          >
            {strings.dashboard.createTicket}
          </Link>
        }
      />

      {query.isPending ? <DashboardSkeleton /> : null}

      {query.isError && !unauthorized ? (
        <ErrorState
          title={strings.dashboard.errorTitle}
          message={strings.dashboard.errorBody}
          retryLabel={strings.common.retry}
          onRetry={() => void query.refetch()}
        />
      ) : null}

      {dashboard ? (
        <div className="space-y-6">
          {dashboard.total_tickets === 0 ? (
            <EmptyState
              title={strings.dashboard.emptyTitle}
              message={strings.dashboard.emptyBody}
              action={
                <Link
                  to="/tickets/nuevo"
                  className="inline-block rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
                >
                  {strings.dashboard.emptyAction}
                </Link>
              }
            />
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <KpiCard
                  label={strings.dashboard.kpis.total}
                  value={dashboard.total_tickets}
                />
                <KpiCard
                  label={strings.dashboard.kpis.open}
                  value={
                    dashboard.by_status.find(
                      (item) => item.status === 'Abierto',
                    )?.count ?? 0
                  }
                />
                <KpiCard
                  label={strings.dashboard.kpis.attention}
                  value={dashboard.by_status
                    .filter(
                      (item) =>
                        item.status === 'Abierto' ||
                        item.status === 'En progreso',
                    )
                    .reduce((total, item) => total + item.count, 0)}
                />
                <KpiCard
                  label={strings.dashboard.kpis.resolved}
                  value={
                    dashboard.by_status.find(
                      (item) => item.status === 'Resuelto',
                    )?.count ?? 0
                  }
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <DistributionCard
                  title={strings.dashboard.byStatus}
                  total={dashboard.total_tickets}
                  items={dashboard.by_status.map((item) => ({
                    label: item.status,
                    count: item.count,
                  }))}
                />
                <DistributionCard
                  title={strings.dashboard.byPriority}
                  total={dashboard.total_tickets}
                  items={dashboard.by_priority.map((item) => ({
                    label: item.label,
                    count: item.count,
                  }))}
                />
              </div>

              <AssigneeCard items={dashboard.by_assignee} />
            </>
          )}

          {dashboard.total_tickets > 0 ? (
            <>
              <SlaCompliancePanel api={api} />
              <RecentTicketsTable tickets={dashboard.recent_tickets} />
            </>
          ) : null}
        </div>
      ) : null}
    </>
  )
}
