import { useEffect, useId, type ReactNode } from 'react'

import { ApiError } from '@/api/httpClient'
import type { SupportMetricsApi } from '@/api/supportMetrics.api'
import ErrorState from '@/components/ui/ErrorState'
import { useSupportMetrics } from '@/hooks/useSupportMetrics'

const numberFormat = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 })

function Metric({
  label, value, children,
}: {
  label: string
  value: string
  children?: ReactNode
}) {
  return (
    <article
      aria-label={label}
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h3 className="text-sm font-medium text-slate-600">{label}</h3>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
      {children ? <div className="mt-2 space-y-1 text-xs text-slate-600">{children}</div> : null}
    </article>
  )
}

/** Presentación HU-18: solo formatea el agregado; no reconstruye indicadores. */
export default function SupportMetricsPanel({
  actorKey, api, onUnauthorized,
}: {
  actorKey: string | null
  api?: SupportMetricsApi
  onUnauthorized?: () => Promise<void>
}) {
  const id = useId()
  const query = useSupportMetrics(actorKey, api)
  const unauthorized = query.error instanceof ApiError && query.error.status === 401

  useEffect(() => {
    if (unauthorized) void onUnauthorized?.().catch(() => undefined)
  }, [onUnauthorized, unauthorized])

  if (query.status === 'idle' || unauthorized) return null
  const data = query.status === 'success' ? query.data : null

  return (
    <section
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-scope`}
      aria-busy={query.status === 'loading'}
      className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-5"
    >
      <h2 id={`${id}-title`} className="text-lg font-semibold text-slate-900">
        Métricas de gestión de soporte
      </h2>
      <p id={`${id}-scope`} className="text-sm text-slate-600">
        Todo el historial autorizado, sin filtros.
      </p>

      {query.status === 'loading' ? (
        <p role="status" className="text-sm text-slate-600">Cargando métricas de soporte…</p>
      ) : null}

      {query.status === 'error' ? (
        query.canRetry ? (
          <ErrorState
            title="No se pudieron cargar las métricas de soporte"
            message="No se pudo completar la consulta. Inténtalo de nuevo."
            retryLabel="Reintentar"
            onRetry={query.retry}
          />
        ) : (
          <p role="alert" className="text-sm text-slate-700">
            Las métricas no están disponibles para esta cuenta.
          </p>
        )
      ) : null}

      {data ? (
        <>
          {data.total_tickets === 0 ? (
            <p role="status" className="text-sm text-slate-600">
              No hay tickets en el historial autorizado.
            </p>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <Metric label="Total de tickets" value={numberFormat.format(data.total_tickets)} />
            <Metric label="Resueltos" value={numberFormat.format(data.resolved_tickets)} />
            <Metric label="Pendientes" value={numberFormat.format(data.pending_tickets)} />
            <Metric
              label="Tiempo promedio de resolución"
              value={data.average_resolution_minutes === null
                ? 'Sin datos'
                : `${numberFormat.format(data.average_resolution_minutes)} minutos`}
            >
              <p>Tickets incluidos en el promedio: {numberFormat.format(data.resolution_sample_size)}</p>
              <p>Finalizados excluidos del promedio: {numberFormat.format(data.resolution_excluded_count)}</p>
            </Metric>
            <Metric
              label="Cumplimiento de SLA de resolución"
              value={data.sla_compliance_percentage === null
                ? 'Sin datos'
                : `${numberFormat.format(data.sla_compliance_percentage)} %`}
            >
              <p>Tickets incluidos en el SLA: {numberFormat.format(data.sla_sample_size)}</p>
              <p>Finalizados excluidos del SLA: {numberFormat.format(data.sla_excluded_count)}</p>
              <p>Resueltos en plazo: {numberFormat.format(data.sla_met_count)}</p>
            </Metric>
          </div>
          <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
            <li>Resueltos incluye Cerrados. Pendientes agrupa los demás estados.</li>
            <li>
              El promedio mide el tiempo continuo desde la creación hasta la resolución, no hasta el cierre.
            </li>
            <li>
              El porcentaje considera solo finalizados con SLA de resolución evaluable y objetivo conservado;
              no incluye pendientes ni primera respuesta.
            </li>
            <li>
              Las muestras indican tickets finalizados incluidos y excluidos, no el total de tickets.
            </li>
            <li>
              Los finalizados sin objetivo conservado se excluyen del SLA, pero mantienen su volumen y su
              promedio cuando sus fechas son válidas. No se utiliza la política vigente para completar objetivos ausentes.
            </li>
          </ul>
        </>
      ) : null}
    </section>
  )
}
