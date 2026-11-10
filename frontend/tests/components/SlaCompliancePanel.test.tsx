import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import SlaCompliancePanel from '@/components/dashboard/SlaCompliancePanel'
import { ApiError } from '@/api/httpClient'
import type { SlaDashboard } from '@/types/dashboard'
import { ADMIN, createAuthApi, renderApp } from '../helpers/renderApp'
import {
  buildEmptySlaDashboard,
  buildSlaDashboard,
  createDashboardApi,
} from '../helpers/dashboardFixtures'

function renderPanel(api = createDashboardApi()) {
  return renderApp(<SlaCompliancePanel api={api} />, { user: ADMIN })
}

describe('SlaCompliancePanel', () => {
  it('muestra el porcentaje, la leyenda, el desglose y las notas reales', async () => {
    renderPanel()

    const panel = await screen.findByRole('region', {
      name: 'Cumplimiento de SLA',
    })
    expect(within(panel).getByText('66.67%')).toBeInTheDocument()
    expect(panel).toHaveTextContent('Últimos 30 días')

    const legend = within(panel).getByRole('list', {
      name: 'Leyenda de estados de SLA',
    })
    const rows = within(legend).getAllByRole('listitem')
    expect(rows).toHaveLength(4)
    expect(rows[0]).toHaveTextContent('En tiempo')
    expect(rows[0]).toHaveTextContent('1')
    expect(rows[1]).toHaveTextContent('En riesgo')
    expect(rows[1]).toHaveTextContent('1')
    expect(rows[2]).toHaveTextContent('Cumplidos')
    expect(rows[2]).toHaveTextContent('3')
    expect(rows[3]).toHaveTextContent('Incumplidos')
    expect(rows[3]).toHaveTextContent('1')

    const priority = within(panel).getByRole('list', {
      name: 'Cumplimiento por prioridad',
    })
    expect(within(priority).getByText('Crítica')).toBeInTheDocument()
    expect(within(priority).getByText('Alta')).toBeInTheDocument()
    expect(within(priority).getByText('Media')).toBeInTheDocument()
    expect(within(priority).getByText('Baja')).toBeInTheDocument()

    expect(
      within(panel).getByText(
        '1 ticket sin SLA (sin prioridad) excluido del cálculo',
      ),
    ).toBeInTheDocument()
    expect(
      within(panel).getByText(
        '1 ticket cerrado sin fecha de resolución se cuenta como cumplido',
      ),
    ).toBeInTheDocument()
  })

  it('recarga al cambiar el periodo y muestra el esqueleto', async () => {
    let resolveSeven: ((value: SlaDashboard) => void) | undefined
    const getSla = vi.fn((days: number) => {
      if (days === 7) {
        return new Promise<SlaDashboard>((resolve) => {
          resolveSeven = resolve
        })
      }
      return Promise.resolve(buildSlaDashboard())
    })
    const api = createDashboardApi({ getSla })
    const user = userEvent.setup()

    renderPanel(api)

    expect(await screen.findByText('66.67%')).toBeInTheDocument()
    const seven = screen.getByRole('button', { name: '7 días' })
    expect(seven).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: '30 días' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    await user.click(seven)

    expect(
      await screen.findByRole('status', {
        name: 'Cargando cumplimiento de SLA',
      }),
    ).toBeInTheDocument()
    expect(getSla).toHaveBeenLastCalledWith(7)
    expect(screen.getByRole('button', { name: '7 días' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    resolveSeven?.(buildSlaDashboard({ period_days: 7, compliance_percentage: 80 }))

    expect(await screen.findByText('80%')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Cumplimiento de SLA' })).toHaveTextContent(
      'Últimos 7 días',
    )
  })

  it('muestra el estado vacío del periodo y conserva el selector', async () => {
    const api = createDashboardApi({
      getSla: vi.fn(async () => buildEmptySlaDashboard()),
    })

    renderPanel(api)

    expect(
      await screen.findByText('No hay tickets evaluables en este periodo'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        '2 tickets sin SLA (sin prioridad) excluidos del cálculo',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '7 días' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '30 días' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '90 días' })).toBeInTheDocument()
  })

  it('muestra el error y reintenta la consulta', async () => {
    const getSla = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(buildSlaDashboard())
    const api = createDashboardApi({ getSla })
    const user = userEvent.setup()

    renderPanel(api)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No se pudo cargar el cumplimiento de SLA')

    await user.click(within(alert).getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('66.67%')).toBeInTheDocument()
    expect(getSla).toHaveBeenCalledTimes(2)
  })

  it('cierra la sesión cuando la consulta responde 401', async () => {
    const api = createDashboardApi({
      getSla: vi.fn(async () => {
        throw new ApiError(401, 'not authenticated')
      }),
    })
    const logout = vi.fn(async () => undefined)

    renderApp(<SlaCompliancePanel api={api} />, {
      user: ADMIN,
      api: createAuthApi(ADMIN, { logout }),
    })

    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1))
    expect(
      screen.queryByRole('region', { name: 'Cumplimiento de SLA' }),
    ).not.toBeInTheDocument()
  })

  it('usa un donut accesible, texto en la leyenda y datos reales sin demo', async () => {
    renderPanel()

    const panel = await screen.findByRole('region', {
      name: 'Cumplimiento de SLA',
    })

    expect(
      within(panel).getByRole('img', {
        name: 'Cumplimiento de SLA: 66.67%',
      }),
    ).toBeInTheDocument()

    const legend = within(panel).getByRole('list', {
      name: 'Leyenda de estados de SLA',
    })
    for (const label of ['En tiempo', 'En riesgo', 'Cumplidos', 'Incumplidos']) {
      expect(within(legend).getByText(label)).toBeInTheDocument()
    }

    expect(panel).not.toHaveTextContent(/demo/i)
    expect(screen.getByRole('button', { name: '30 días' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})
