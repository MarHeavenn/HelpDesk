import { useEffect, useState } from 'react'

import type { DashboardApi } from '@/api/dashboard.api'
import { ApiError } from '@/api/httpClient'
import ErrorState from '@/components/ui/ErrorState'
import Skeleton from '@/components/ui/Skeleton'
import { useAuth } from '@/context/AuthContext'
import { useSlaDashboard } from '@/hooks/useDashboard'
import { formatPercent } from '@/lib/format'
import { strings } from '@/lib/strings'
import type { SlaDashboard } from '@/types/dashboard'

const PERIODS = [7, 30, 90] as const
type Period = (typeof PERIODS)[number]

type SlaStateKey = 'en_tiempo' | 'en_riesgo' | 'cumplido' | 'incumplido'

const STATE_ROWS: {
  key: SlaStateKey
  color: string
  dotClass: string
}[] = [
  { key: 'en_tiempo', color: '#10b981', dotClass: 'bg-emerald-500' },
  { key: 'en_riesgo', color: '#f59e0b', dotClass: 'bg-amber-500' },
  { key: 'cumplido', color: '#4f46e5', dotClass: 'bg-primary' },
  { key: 'incumplido', color: '#ef4444', dotClass: 'bg-red-500' },
]

/** Donut SVG con el porcentaje de cumplimiento al centro (RF-102, RF-103). */
function SlaDonut({ data }: { data: SlaDashboard }) {
  const radius = 40
  const circumference = 2 * Math.PI * radius
  let consumed = 0

  return (
    <div
      role="img"
      aria-label={strings.dashboard.sla.donutLabel(
        formatPercent(data.compliance_percentage),
      )}
      className="relative mx-auto h-40 w-40 shrink-0"
    >
      <svg
        viewBox="0 0 100 100"
        aria-hidden="true"
        className="h-full w-full -rotate-90"
      >
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="12"
        />
        {STATE_ROWS.map((row) => {
          const value = data[row.key]
          const length =
            data.total_evaluated > 0
              ? (value / data.total_evaluated) * circumference
              : 0
          const offset = consumed
          consumed += length

          if (value === 0) return null

          return (
            <circle
              key={row.key}
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              stroke={row.color}
              strokeWidth="12"
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={-offset}
            />
          )
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-3xl font-semibold tracking-tight text-slate-900">
          {formatPercent(data.compliance_percentage)}
        </span>
        <span className="mt-1 text-xs font-medium text-slate-500">
          {strings.dashboard.sla.compliance}
        </span>
      </div>
    </div>
  )
}

/** Esqueleto del panel mientras se consulta el periodo (RF-103). */
function SlaPanelSkeleton() {
  return (
    <div
      role="status"
      aria-label={strings.dashboard.sla.loading}
      className="grid gap-6 lg:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]"
    >
      <Skeleton className="mx-auto h-40 w-40 rounded-full" />
      <div className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-2/3" />
      </div>
    </div>
  )
}

/**
 * Panel de cumplimiento de SLA del dashboard (RF-102 a RF-104).
 *
 * Consume el contrato real `GET /api/dashboard/sla`, reutiliza el cálculo
 * del módulo `sla` y permite alternar el periodo entre 7, 30 y 90 días.
 */
export default function SlaCompliancePanel({ api }: { api?: DashboardApi }) {
  const { logout } = useAuth()
  const [days, setDays] = useState<Period>(30)
  const query = useSlaDashboard(days, api)
  const dashboard = query.data

  const unauthorized =
    query.error instanceof ApiError && query.error.status === 401

  useEffect(() => {
    if (!unauthorized) return
    void logout().catch(() => undefined)
  }, [logout, unauthorized])

  if (unauthorized) return null

  return (
    <section
      aria-label={strings.dashboard.sla.title}
      className="rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            {strings.dashboard.sla.title}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {strings.dashboard.sla.subtitle(days)}
            {dashboard
              ? ` · ${strings.dashboard.sla.threshold(
                  dashboard.threshold_percent,
                )}`
              : null}
          </p>
        </div>

        <div
          role="group"
          aria-label={strings.dashboard.sla.periodLabel}
          className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1"
        >
          {PERIODS.map((period) => (
            <button
              key={period}
              type="button"
              aria-pressed={days === period}
              onClick={() => setDays(period)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                days === period
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {strings.dashboard.sla.period(period)}
            </button>
          ))}
        </div>
      </header>

      <div className="p-5">
        {query.isPending ? <SlaPanelSkeleton /> : null}

        {query.isError && !unauthorized ? (
          <ErrorState
            title={strings.dashboard.sla.errorTitle}
            message={strings.dashboard.sla.errorBody}
            retryLabel={strings.common.retry}
            onRetry={() => void query.refetch()}
          />
        ) : null}

        {dashboard ? (
          <>
            {dashboard.total_evaluated === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
                <p className="text-base font-semibold text-slate-900">
                  {strings.dashboard.sla.emptyTitle}
                </p>
                <p className="mx-auto mt-1 max-w-md text-sm text-slate-600">
                  {strings.dashboard.sla.emptyBody}
                </p>
              </div>
            ) : (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
                <SlaDonut data={dashboard} />

                <div className="space-y-5">
                  <ul
                    aria-label={strings.dashboard.sla.legendLabel}
                    className="space-y-2"
                  >
                    {STATE_ROWS.map((row) => (
                      <li
                        key={row.key}
                        className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm"
                      >
                        <span className="flex items-center gap-2 font-medium text-slate-700">
                          <span
                            aria-hidden="true"
                            className={`h-2.5 w-2.5 rounded-full ${row.dotClass}`}
                          />
                          {strings.dashboard.sla.states[row.key]}
                        </span>
                        <span className="font-semibold text-slate-900">
                          {dashboard[row.key]}
                        </span>
                      </li>
                    ))}
                  </ul>

                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">
                      {strings.dashboard.sla.byPriority}
                    </h3>
                    <ul
                      aria-label={strings.dashboard.sla.byPriority}
                      className="mt-2 divide-y divide-slate-100"
                    >
                      {dashboard.by_priority.map((item) => {
                        const evaluated =
                          item.en_tiempo +
                          item.en_riesgo +
                          item.cumplido +
                          item.incumplido
                        return (
                          <li
                            key={item.priority}
                            className="flex items-center justify-between gap-3 py-2 text-sm"
                          >
                            <span className="font-medium text-slate-700">
                              {item.priority}
                            </span>
                            <span className="flex items-center gap-3 text-slate-500">
                              <span>
                                {strings.dashboard.sla.priorityEvaluated(
                                  evaluated,
                                )}
                              </span>
                              <span className="w-16 text-right font-semibold text-slate-900">
                                {formatPercent(item.compliance_percentage)}
                              </span>
                            </span>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            <div className="mt-5 space-y-1 border-t border-slate-100 pt-4 text-xs text-slate-500">
              <p>{strings.dashboard.sla.withoutSla(dashboard.sin_sla)}</p>
              {dashboard.closed_without_resolved_at > 0 ? (
                <p>
                  {strings.dashboard.sla.closedWithoutResolvedAt(
                    dashboard.closed_without_resolved_at,
                  )}
                </p>
              ) : null}
            </div>
          </>
        ) : null}
      </div>
    </section>
  )
}
