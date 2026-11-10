import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { createAuthApi } from '../helpers/renderApp'
import DashboardPage from '@/pages/DashboardPage'
import { ApiError } from '@/api/httpClient'
import { ADMIN, renderApp } from '../helpers/renderApp'
import {
  buildSlaDashboard,
  buildTicketDashboard,
  createDashboardApi,
} from '../helpers/dashboardFixtures'
import type { TicketDashboard } from '@/types/dashboard'

function renderPage(api = createDashboardApi()) {
  return renderApp(<DashboardPage api={api} />, { user: ADMIN })
}

describe('DashboardPage', () => {
  it('muestra indicadores, distribuciones, carga y tickets recientes reales', async () => {
    renderPage()

    expect(
      await screen.findByRole('article', { name: 'Total de tickets' }),
    ).toHaveTextContent('6')
    expect(
      screen.getByRole('article', { name: 'Abiertos' }),
    ).toHaveTextContent('2')
    expect(
      screen.getByRole('article', { name: 'En atención' }),
    ).toHaveTextContent('4')
    expect(
      screen.getByRole('article', { name: 'Resueltos' }),
    ).toHaveTextContent('1')

    const status = screen.getByRole('region', {
      name: 'Distribución por estado',
    })
    expect(within(status).getByText('Abierto')).toBeInTheDocument()
    expect(within(status).getAllByText('2 · 33%')).toHaveLength(2)
    expect(within(status).getAllByText('1 · 17%')).toHaveLength(2)

    const priority = screen.getByRole('region', {
      name: 'Distribución por prioridad',
    })
    expect(within(priority).getByText('Sin prioridad')).toBeInTheDocument()
    expect(within(priority).getByText('Crítica')).toBeInTheDocument()

    const assignees = screen.getByRole('region', { name: 'Carga por técnico' })
    expect(within(assignees).getByText('Sin asignar')).toBeInTheDocument()
    expect(within(assignees).getByText('Ana')).toBeInTheDocument()
    expect(within(assignees).getByText('Luis')).toBeInTheDocument()

    const table = screen.getByRole('table', { name: 'Tickets recientes' })
    expect(within(table).getAllByRole('row')).toHaveLength(6)
    expect(
      within(table).getByText('No puedo iniciar sesión'),
    ).toBeInTheDocument()
    expect(within(table).getByText('#TICKET-1')).toBeInTheDocument()

    expect(
      screen.getByRole('link', { name: '+ Crear ticket' }),
    ).toHaveAttribute('href', '/tickets/nuevo')
    expect(screen.getByRole('link', { name: 'Ver todos' })).toHaveAttribute(
      'href',
      '/tickets',
    )

    const sla = await screen.findByRole('region', {
      name: 'Cumplimiento de SLA',
    })
    expect(await within(sla).findByText('66.67%')).toBeInTheDocument()
  })

  it('muestra esqueletos mientras carga el resumen', async () => {
    const api = createDashboardApi({
      getTickets: vi.fn(
        () => new Promise<TicketDashboard>(() => undefined),
      ),
    })

    renderPage(api)

    expect(
      await screen.findByRole('status', { name: 'Cargando dashboard' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('article', { name: 'Total de tickets' }),
    ).not.toBeInTheDocument()
  })

  it('muestra el estado vacío con enlace a crear ticket', async () => {
    const api = createDashboardApi({
      getTickets: vi.fn(async () =>
        buildTicketDashboard({
          total_tickets: 0,
          by_status: [
            { status: 'Abierto', count: 0 },
            { status: 'En progreso', count: 0 },
            { status: 'Resuelto', count: 0 },
            { status: 'Cerrado', count: 0 },
          ],
          by_priority: [
            { priority: 'Crítica', label: 'Crítica', count: 0 },
            { priority: 'Alta', label: 'Alta', count: 0 },
            { priority: 'Media', label: 'Media', count: 0 },
            { priority: 'Baja', label: 'Baja', count: 0 },
            { priority: null, label: 'Sin prioridad', count: 0 },
          ],
          by_assignee: [
            { technician: null, label: 'Sin asignar', count: 0 },
          ],
          recent_tickets: [],
        }),
      ),
    })

    renderPage(api)

    expect(await screen.findByText('Aún no hay tickets')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Crear ticket' })).toHaveAttribute(
      'href',
      '/tickets/nuevo',
    )
  })

  it('muestra el error y reintenta la consulta', async () => {
    const getTickets = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(buildTicketDashboard())
    const api = createDashboardApi({ getTickets })
    const user = userEvent.setup()

    renderPage(api)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No se pudo cargar el dashboard')

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(
      await screen.findByRole('article', { name: 'Total de tickets' }),
    ).toHaveTextContent('6')
    expect(getTickets).toHaveBeenCalledTimes(2)
  })

  it('cierra la sesión cuando la consulta responde 401', async () => {
    const api = createDashboardApi({
      getTickets: vi.fn(async () => {
        throw new ApiError(401, 'not authenticated')
      }),
    })
    const logout = vi.fn(async () => undefined)

    renderApp(<DashboardPage api={api} />, {
      user: ADMIN,
      api: createAuthApi(ADMIN, { logout }),
    })

    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1))
    expect(
      screen.queryByText('No se pudo cargar el dashboard'),
    ).not.toBeInTheDocument()
  })

  it('respeta el alcance del técnico que devuelve el contrato', async () => {
    const api = createDashboardApi({
      getTickets: vi.fn(async () =>
        buildTicketDashboard({
          total_tickets: 2,
          by_status: [
            { status: 'Abierto', count: 1 },
            { status: 'En progreso', count: 1 },
            { status: 'Resuelto', count: 0 },
            { status: 'Cerrado', count: 0 },
          ],
          by_priority: [
            { priority: 'Crítica', label: 'Crítica', count: 0 },
            { priority: 'Alta', label: 'Alta', count: 1 },
            { priority: 'Media', label: 'Media', count: 1 },
            { priority: 'Baja', label: 'Baja', count: 0 },
            { priority: null, label: 'Sin prioridad', count: 0 },
          ],
          by_assignee: [
            { technician: null, label: 'Sin asignar', count: 0 },
            {
              technician: { id: 'u-tech', name: 'Tomás Técnico' },
              label: 'Tomás Técnico',
              count: 2,
            },
          ],
          recent_tickets: buildTicketDashboard().recent_tickets.slice(0, 2),
        }),
      ),
    })

    renderPage(api)

    const assignees = await screen.findByRole('region', {
      name: 'Carga por técnico',
    })
    expect(within(assignees).getByText('Tomás Técnico')).toBeInTheDocument()
    expect(within(assignees).queryByText('Luis')).not.toBeInTheDocument()
  })

  it('integra el panel de SLA y consulta el periodo elegido', async () => {
    const getSla = vi.fn(async (days: number) =>
      buildSlaDashboard({
        period_days: days,
        compliance_percentage: days === 7 ? 80 : 66.67,
      }),
    )
    const api = createDashboardApi({ getSla })
    const user = userEvent.setup()

    renderPage(api)

    const panel = await screen.findByRole('region', {
      name: 'Cumplimiento de SLA',
    })
    expect(await within(panel).findByText('66.67%')).toBeInTheDocument()

    await user.click(within(panel).getByRole('button', { name: '7 días' }))

    expect(await within(panel).findByText('80%')).toBeInTheDocument()
    expect(getSla).toHaveBeenLastCalledWith(7)
  })

  it('cierra la sesión cuando el panel de SLA responde 401', async () => {
    const api = createDashboardApi({
      getSla: vi.fn(async () => {
        throw new ApiError(401, 'not authenticated')
      }),
    })
    const logout = vi.fn(async () => undefined)

    renderApp(<DashboardPage api={api} />, {
      user: ADMIN,
      api: createAuthApi(ADMIN, { logout }),
    })

    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1))
  })
})
