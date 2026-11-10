import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/httpClient'
import { useSlaDashboard, useTicketsDashboard } from '@/hooks/useDashboard'
import {
  buildSlaDashboard,
  buildTicketDashboard,
  createDashboardApi,
} from '../helpers/dashboardFixtures'

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

function createClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
}

describe('useDashboard', () => {
  it('devuelve el resumen de tickets', async () => {
    const payload = buildTicketDashboard()
    const api = createDashboardApi({
      getTickets: vi.fn(async () => payload),
    })

    const { result } = renderHook(() => useTicketsDashboard(api), {
      wrapper: wrapper(createClient()),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(payload)
  })

  it('expone el 401 como error de la consulta de tickets', async () => {
    const error = new ApiError(401, 'not authenticated')
    const api = createDashboardApi({
      getTickets: vi.fn(async () => {
        throw error
      }),
    })

    const { result } = renderHook(() => useTicketsDashboard(api), {
      wrapper: wrapper(createClient()),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBe(error)
  })

  it('expone el 404 como error de la consulta de tickets', async () => {
    const error = new ApiError(404, 'tickets not found')
    const api = createDashboardApi({
      getTickets: vi.fn(async () => {
        throw error
      }),
    })

    const { result } = renderHook(() => useTicketsDashboard(api), {
      wrapper: wrapper(createClient()),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBe(error)
  })

  it('expone los errores de red sin reintentos automáticos', async () => {
    const getTickets = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    const api = createDashboardApi({ getTickets })

    const { result } = renderHook(() => useTicketsDashboard(api), {
      wrapper: wrapper(createClient()),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(getTickets).toHaveBeenCalledTimes(1)
  })

  it('consulta el SLA con el periodo recibido', async () => {
    const payload = buildSlaDashboard({ period_days: 7 })
    const getSla = vi.fn(async () => payload)
    const api = createDashboardApi({ getSla })

    const { result } = renderHook(() => useSlaDashboard(7, api), {
      wrapper: wrapper(createClient()),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(getSla).toHaveBeenCalledWith(7)
    expect(result.current.data?.period_days).toBe(7)
  })
})
