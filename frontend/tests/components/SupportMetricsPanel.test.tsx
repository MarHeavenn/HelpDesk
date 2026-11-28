import { act, cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import SupportMetricsPanel from '@/components/dashboard/SupportMetricsPanel'
import { ApiError } from '@/api/httpClient'
import type { SupportMetrics } from '@/types/supportMetrics'
import { buildSupportMetrics } from '../helpers/supportMetricsFixtures'

afterEach(cleanup)

function apiWith(payload: SupportMetrics) {
  return { getMetrics: vi.fn().mockResolvedValue(payload) }
}

function metric(panel: HTMLElement, name: string) {
  return within(panel).getByRole('article', { name })
}

function deferred() {
  let resolve!: (value: SupportMetrics) => void
  const promise = new Promise<SupportMetrics>((yes) => { resolve = yes })
  return { promise, resolve }
}

async function ready() {
  await screen.findByText('Tickets incluidos en el promedio:', { exact: false })
  return screen.getByRole('region', { name: 'Métricas de gestión de soporte' })
}

describe('SupportMetricsPanel', () => {
  it('presenta juntos los cinco indicadores y las muestras del ejemplo de cinco tickets', async () => {
    const payload = buildSupportMetrics({
      total_tickets: 5, resolved_tickets: 3, pending_tickets: 2,
      average_resolution_minutes: 90, resolution_sample_size: 2,
      resolution_excluded_count: 1,
    })
    render(<SupportMetricsPanel actorKey="admin-a" api={apiWith(payload)} />)
    const panel = await ready()

    expect(within(panel).getAllByRole('article')).toHaveLength(5)
    expect(metric(panel, 'Total de tickets')).toHaveTextContent('5')
    expect(metric(panel, 'Resueltos')).toHaveTextContent('3')
    expect(metric(panel, 'Pendientes')).toHaveTextContent('2')
    const average = metric(panel, 'Tiempo promedio de resolución')
    expect(average).toHaveTextContent('90 minutos')
    expect(average).toHaveTextContent('Tickets incluidos en el promedio: 2')
    expect(average).toHaveTextContent('Finalizados excluidos del promedio: 1')
    const sla = metric(panel, 'Cumplimiento de SLA de resolución')
    expect(sla).toHaveTextContent('50 %')
    expect(sla).toHaveTextContent('Tickets incluidos en el SLA: 2')
    expect(sla).toHaveTextContent('Finalizados excluidos del SLA: 1')
    expect(sla).toHaveTextContent('Resueltos en plazo: 1')
    expect(panel).toHaveTextContent('Todo el historial autorizado, sin filtros')
    expect(panel).toHaveTextContent('Resueltos incluye Cerrados')
    expect(panel).toHaveTextContent('desde la creación hasta la resolución, no hasta el cierre')
    expect(panel).toHaveTextContent('solo finalizados con SLA de resolución evaluable y objetivo conservado')
    expect(panel).toHaveTextContent('no incluye pendientes ni primera respuesta')
    expect(panel).toHaveTextContent('sin objetivo conservado se excluyen del SLA')
    expect(panel).toHaveTextContent('No se utiliza la política vigente')
    expect(within(panel).queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('distingue población y muestras independientes del ejemplo 120 minutos/50 %', async () => {
    render(<SupportMetricsPanel actorKey="admin-a" api={apiWith(buildSupportMetrics())} />)
    const panel = await ready()

    expect(metric(panel, 'Tiempo promedio de resolución')).toHaveTextContent('120 minutos')
    expect(metric(panel, 'Tiempo promedio de resolución')).toHaveTextContent('Tickets incluidos en el promedio: 3')
    expect(metric(panel, 'Tiempo promedio de resolución')).toHaveTextContent('Finalizados excluidos del promedio: 0')
    expect(metric(panel, 'Cumplimiento de SLA de resolución')).toHaveTextContent('Tickets incluidos en el SLA: 2')
    expect(metric(panel, 'Cumplimiento de SLA de resolución')).toHaveTextContent('Finalizados excluidos del SLA: 1')
  })

  it('sin objetivo conservado conserva el promedio válido y muestra SLA Sin datos', async () => {
    render(<SupportMetricsPanel actorKey="admin-a" api={apiWith(buildSupportMetrics({
      total_tickets: 1, resolved_tickets: 1, average_resolution_minutes: 180,
      resolution_sample_size: 1, sla_compliance_percentage: null,
      sla_sample_size: 0, sla_met_count: 0, sla_excluded_count: 1,
    }))} />)
    const panel = await ready()

    expect(metric(panel, 'Tiempo promedio de resolución')).toHaveTextContent('180 minutos')
    const sla = metric(panel, 'Cumplimiento de SLA de resolución')
    expect(sla).toHaveTextContent('Sin datos')
    expect(sla).toHaveTextContent('Tickets incluidos en el SLA: 0')
    expect(sla).toHaveTextContent('Finalizados excluidos del SLA: 1')
    expect(within(panel).getAllByText('Sin datos')).toHaveLength(1)
  })

  it('cero con muestra positiva no se transforma en Sin datos', async () => {
    render(<SupportMetricsPanel actorKey="admin-a" api={apiWith(buildSupportMetrics({
      total_tickets: 1, resolved_tickets: 1, average_resolution_minutes: 0,
      resolution_sample_size: 1, sla_compliance_percentage: 0,
      sla_sample_size: 1, sla_met_count: 0, sla_excluded_count: 0,
    }))} />)
    const panel = await ready()

    expect(metric(panel, 'Tiempo promedio de resolución')).toHaveTextContent('0 minutos')
    expect(metric(panel, 'Cumplimiento de SLA de resolución')).toHaveTextContent('0 %')
    expect(within(panel).queryByText('Sin datos')).not.toBeInTheDocument()
  })

  it('formatea en español hasta dos decimales sin alterar ni recalcular el agregado', async () => {
    const payload = buildSupportMetrics({
      average_resolution_minutes: 90.126, sla_compliance_percentage: 66.67,
    })
    const before = { ...payload }
    render(<SupportMetricsPanel actorKey="admin-a" api={apiWith(payload)} />)
    const panel = await ready()

    expect(within(panel).getByText('90,13 minutos')).toBeInTheDocument()
    expect(within(panel).getByText('66,67 %')).toBeInTheDocument()
    expect(payload).toEqual(before)
  })

  it('carga sin indicadores, cifras provisionales ni Sin datos ficticio', () => {
    const pending = deferred()
    render(<SupportMetricsPanel actorKey="admin-a" api={{ getMetrics: vi.fn(() => pending.promise) }} />)
    const panel = screen.getByRole('region', { name: 'Métricas de gestión de soporte' })

    expect(panel).toHaveAttribute('aria-busy', 'true')
    expect(within(panel).getByRole('status')).toHaveTextContent('Cargando métricas de soporte')
    expect(within(panel).queryByRole('article')).not.toBeInTheDocument()
    expect(within(panel).queryByText('Sin datos')).not.toBeInTheDocument()
  })

  it('vacío muestra aviso, tres ceros y dos Sin datos con muestras cero', async () => {
    render(<SupportMetricsPanel actorKey="admin-a" api={apiWith(buildSupportMetrics({
      total_tickets: 0, resolved_tickets: 0, pending_tickets: 0,
      average_resolution_minutes: null, resolution_sample_size: 0,
      resolution_excluded_count: 0, sla_compliance_percentage: null,
      sla_sample_size: 0, sla_met_count: 0, sla_excluded_count: 0,
    }))} />)
    const panel = await ready()

    expect(panel).toHaveAttribute('aria-busy', 'false')
    expect(within(panel).getByRole('status')).toHaveTextContent('No hay tickets en el historial autorizado')
    expect(within(panel).getAllByText('0', { exact: true })).toHaveLength(3)
    expect(within(panel).getAllByText('Sin datos')).toHaveLength(2)
    expect(metric(panel, 'Tiempo promedio de resolución')).toHaveTextContent('Tickets incluidos en el promedio: 0')
    expect(metric(panel, 'Cumplimiento de SLA de resolución')).toHaveTextContent('Finalizados excluidos del SLA: 0')
  })

  it('solo pendientes no equivale a historial vacío aunque no haya muestras', async () => {
    render(<SupportMetricsPanel actorKey="admin-a" api={apiWith(buildSupportMetrics({
      total_tickets: 5, resolved_tickets: 0, pending_tickets: 5,
      average_resolution_minutes: null, resolution_sample_size: 0,
      resolution_excluded_count: 0, sla_compliance_percentage: null,
      sla_sample_size: 0, sla_met_count: 0, sla_excluded_count: 0,
    }))} />)
    const panel = await ready()

    expect(within(panel).getAllByText('Sin datos')).toHaveLength(2)
    expect(metric(panel, 'Pendientes')).toHaveTextContent('5')
    expect(within(panel).queryByText(/No hay tickets/)).not.toBeInTheDocument()
  })

  it('fallo técnico no se presenta como vacío y se reintenta con teclado', async () => {
    const recovered = deferred()
    const api = { getMetrics: vi.fn().mockRejectedValueOnce(new TypeError('private failure'))
      .mockReturnValueOnce(recovered.promise) }
    const user = userEvent.setup()
    render(<SupportMetricsPanel actorKey="admin-a" api={api} />)
    const alert = await screen.findByRole('alert')

    expect(alert).toHaveTextContent('No se pudieron cargar las métricas de soporte')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    expect(screen.queryByText('Sin datos')).not.toBeInTheDocument()
    expect(screen.queryByText(/No hay tickets/)).not.toBeInTheDocument()
    expect(screen.queryByText('private failure')).not.toBeInTheDocument()
    await user.tab()
    expect(within(alert).getByRole('button', { name: 'Reintentar' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('status')).toHaveTextContent('Cargando métricas de soporte')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    await act(async () => recovered.resolve(buildSupportMetrics()))
    expect(metric(await ready(), 'Tiempo promedio de resolución')).toHaveTextContent('120 minutos')
    expect(api.getMetrics).toHaveBeenCalledTimes(2)
  })

  it('al fallar una nueva carga no conserva cifras previas como actuales', async () => {
    const api = apiWith(buildSupportMetrics({ average_resolution_minutes: 123.45 }))
    const next = deferred()
    const nextApi = { getMetrics: vi.fn(() => next.promise) }
    const view = render(<SupportMetricsPanel actorKey="admin-a" api={api} />)
    await ready()
    expect(screen.getByText('123,45 minutos')).toBeInTheDocument()
    view.rerender(<SupportMetricsPanel actorKey="admin-a" api={nextApi} />)
    expect(screen.queryByText('123,45 minutos')).not.toBeInTheDocument()
    view.rerender(<SupportMetricsPanel actorKey="admin-a" api={{
      getMetrics: vi.fn().mockRejectedValue(new ApiError(500, 'failure')),
    }} />)

    await screen.findByRole('alert')
    expect(screen.queryByText('123,45 minutos')).not.toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('un 404 presenta indisponibilidad sin datos ni reintento de elevación', async () => {
    render(<SupportMetricsPanel actorKey="admin-a" api={{
      getMetrics: vi.fn().mockRejectedValue(new ApiError(404, 'not found')),
    }} />)
    const alert = await screen.findByRole('alert')

    expect(alert).toHaveTextContent('Las métricas no están disponibles para esta cuenta')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
  })

  it('asocia región, encabezado y alcance con identificadores accesibles únicos', async () => {
    render(<>
      <SupportMetricsPanel actorKey="admin-a" api={apiWith(buildSupportMetrics())} />
      <SupportMetricsPanel actorKey="admin-b" api={apiWith(buildSupportMetrics())} />
    </>)
    await screen.findAllByText('120 minutos')
    const panels = screen.getAllByRole('region', { name: 'Métricas de gestión de soporte' })
    const ids = panels.map((panel) => panel.getAttribute('aria-labelledby'))
    expect(new Set(ids).size).toBe(2)
    for (const panel of panels) {
      expect(within(panel).getByRole('heading', { level: 2 })).toHaveTextContent('Métricas de gestión de soporte')
      expect(document.getElementById(panel.getAttribute('aria-describedby')!))
        .toHaveTextContent('Todo el historial autorizado, sin filtros')
      expect(within(panel).getAllByRole('article')).toHaveLength(5)
    }
  })
})
