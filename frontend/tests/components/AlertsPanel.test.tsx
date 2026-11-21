import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import AlertsPanel from '@/components/dashboard/AlertsPanel'
import { ApiError } from '@/api/httpClient'
import {
  ADMIN,
  CLIENTE,
  createAuthApi,
  renderApp,
} from '../helpers/renderApp'
import { buildAttentionTickets, createDashboardApi } from '../helpers/dashboardFixtures'

function renderPanel(api = createDashboardApi(), user = ADMIN) {
  return renderApp(<AlertsPanel api={api} />, { user })
}

describe('AlertsPanel', () => {
  it('muestra el resumen y la lista en el orden que devuelve la API', async () => {
    renderPanel()

    const panel = await screen.findByRole('region', { name: 'Alertas de SLA' })
    expect(panel).toHaveTextContent('Tickets que requieren atención ahora')

    const summary = await within(panel).findByRole('list', {
      name: 'Resumen de alertas',
    })
    const counts = within(summary).getAllByRole('listitem')
    expect(counts[0]).toHaveTextContent('Próximos a vencer')
    expect(counts[0]).toHaveTextContent('1')
    expect(counts[1]).toHaveTextContent('Vencidos')
    expect(counts[1]).toHaveTextContent('1')

    const list = within(panel).getByRole('list', { name: 'Tickets en alerta' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('Servidor caído')
    expect(rows[0]).toHaveTextContent('Próximo a vencer')
    expect(rows[1]).toHaveTextContent('Error de facturación')
    expect(rows[1]).toHaveTextContent('Vencido')

    const links = within(list).getAllByRole('link', {
      name: /Ver detalle del ticket/,
    })
    expect(links[0]).toHaveAttribute('href', '/tickets?q=ticket-risk')
    expect(links[1]).toHaveAttribute('href', '/tickets?q=ticket-breach')
  })

  it('usa regiones y enlaces etiquetados, sin datos de demostración', async () => {
    renderPanel()

    const panel = await screen.findByRole('region', { name: 'Alertas de SLA' })
    expect(panel).not.toHaveTextContent(/demo/i)
    const links = await within(panel).findAllByRole('link', {
      name: /Ver detalle del ticket/,
    })
    expect(links).toHaveLength(2)
    expect(links[0]).toHaveAttribute('href', '/tickets?q=ticket-risk')
  })

  it('muestra el estado vacío sin lista', async () => {
    const api = createDashboardApi({
      getAttention: vi.fn(async () => []),
    })

    renderPanel(api)

    expect(
      await screen.findByText('No hay tickets que requieran atención'),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('list', { name: 'Tickets en alerta' }),
    ).not.toBeInTheDocument()
  })

  it('muestra el error y reintenta la consulta', async () => {
    const getAttention = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(buildAttentionTickets())
    const api = createDashboardApi({ getAttention })
    const user = userEvent.setup()

    renderPanel(api)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No se pudo cargar las alertas')

    await user.click(within(alert).getByRole('button', { name: 'Reintentar' }))

    expect(
      await screen.findByRole('list', { name: 'Tickets en alerta' }),
    ).toBeInTheDocument()
    expect(getAttention).toHaveBeenCalledTimes(2)
  })

  it('cierra la sesión cuando la consulta responde 401', async () => {
    const api = createDashboardApi({
      getAttention: vi.fn(async () => {
        throw new ApiError(401, 'not authenticated')
      }),
    })
    const logout = vi.fn(async () => undefined)

    renderApp(<AlertsPanel api={api} />, {
      user: ADMIN,
      api: createAuthApi(ADMIN, { logout }),
    })

    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1))
    expect(
      screen.queryByRole('region', { name: 'Alertas de SLA' }),
    ).not.toBeInTheDocument()
  })

  it('no consulta ni renderiza el panel para el cliente', () => {
    const getAttention = vi.fn(async () => buildAttentionTickets())
    const api = createDashboardApi({ getAttention })

    renderPanel(api, CLIENTE)

    expect(getAttention).not.toHaveBeenCalled()
    expect(
      screen.queryByRole('region', { name: 'Alertas de SLA' }),
    ).not.toBeInTheDocument()
  })
})
