import { describe, expect, it, vi } from 'vitest'

import { createDashboardApi, type RequestFn } from '@/api/dashboard.api'
import { ApiError } from '@/api/httpClient'
import {
  buildSlaDashboard,
  buildTicketDashboard,
} from '../helpers/dashboardFixtures'

function requestMock(): RequestFn {
  return vi.fn() as unknown as RequestFn
}

describe('dashboard.api', () => {
  it('consulta el resumen de tickets en el contrato de HU-11', async () => {
    const payload = buildTicketDashboard()
    const http = vi.fn(async () => payload) as unknown as RequestFn
    const api = createDashboardApi(http)

    await expect(api.getTickets()).resolves.toBe(payload)
    expect(http).toHaveBeenCalledWith('/api/dashboard/tickets')
  })

  it('consulta el cumplimiento de SLA con el periodo indicado', async () => {
    const payload = buildSlaDashboard({ period_days: 7 })
    const http = vi.fn(async () => payload) as unknown as RequestFn
    const api = createDashboardApi(http)

    await expect(api.getSla(7)).resolves.toBe(payload)
    expect(http).toHaveBeenCalledWith('/api/dashboard/sla?days=7')
  })

  it('propaga el 401 tipado del cliente HTTP', async () => {
    const error = new ApiError(401, 'not authenticated')
    const http = requestMock()
    vi.mocked(http).mockRejectedValue(error)

    await expect(createDashboardApi(http).getTickets()).rejects.toBe(error)
  })

  it('propaga el 404 del alcance denegado', async () => {
    const error = new ApiError(404, 'tickets not found')
    const http = requestMock()
    vi.mocked(http).mockRejectedValue(error)

    await expect(createDashboardApi(http).getSla(30)).rejects.toBe(error)
  })

  it('propaga un error de red sin transformarlo', async () => {
    const error = new TypeError('Failed to fetch')
    const http = requestMock()
    vi.mocked(http).mockRejectedValue(error)

    await expect(createDashboardApi(http).getTickets()).rejects.toBe(error)
  })
})
