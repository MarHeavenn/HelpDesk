import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, request, setUnauthorizedHandler } from '@/api/httpClient'
import { buildSupportMetrics } from '../helpers/supportMetricsFixtures'

afterEach(() => {
  setUnauthorizedHandler(null)
  vi.unstubAllGlobals()
})

describe('supportMetrics.api', () => {
  it('pide una sola vez el agregado, sin filtros ni periodo ni paginación', async () => {
    const { createSupportMetricsApi } = await import('@/api/supportMetrics.api')
    const payload = buildSupportMetrics({ average_resolution_minutes: 120.123456 })
    const http = vi.fn().mockResolvedValue(payload) as unknown as typeof request

    await expect(createSupportMetricsApi(http).getMetrics()).resolves.toBe(payload)
    expect(http).toHaveBeenCalledTimes(1)
    expect(http).toHaveBeenCalledWith('/api/dashboard/support-metrics')
  })

  it.each([null, 0])('conserva %s y los diez campos sin recalcular', async (value) => {
    const { createSupportMetricsApi } = await import('@/api/supportMetrics.api')
    const payload = buildSupportMetrics({
      average_resolution_minutes: value,
      sla_compliance_percentage: value,
    })
    const http = vi.fn().mockResolvedValue(payload) as unknown as typeof request

    const result = await createSupportMetricsApi(http).getMetrics()

    expect(result).toBe(payload)
    expect(Object.keys(result)).toHaveLength(10)
    expect(result.average_resolution_minutes).toBe(value)
    expect(result.sla_compliance_percentage).toBe(value)
  })

  it('permite cancelar la lectura sin añadir parámetros al endpoint', async () => {
    const { createSupportMetricsApi } = await import('@/api/supportMetrics.api')
    const controller = new AbortController()
    const http = vi.fn().mockResolvedValue(buildSupportMetrics()) as unknown as typeof request

    await createSupportMetricsApi(http).getMetrics(controller.signal)

    expect(http).toHaveBeenCalledTimes(1)
    expect(http).toHaveBeenCalledWith(
      '/api/dashboard/support-metrics', { signal: controller.signal },
    )
  })

  it.each([
    new ApiError(401, 'not authenticated'),
    new ApiError(404, 'not found'),
    new ApiError(500, 'technical failure'),
    new TypeError('Failed to fetch'),
  ])('propaga el error sin sustituirlo por datos vacíos: %s', async (error) => {
    const { createSupportMetricsApi } = await import('@/api/supportMetrics.api')
    const http = vi.fn().mockRejectedValue(error) as unknown as typeof request

    await expect(createSupportMetricsApi(http).getMetrics()).rejects.toBe(error)
    expect(http).toHaveBeenCalledTimes(1)
  })

  it('reutiliza el cliente HTTP con cookie de sesión y sin query string', async () => {
    const { supportMetricsApi } = await import('@/api/supportMetrics.api')
    const payload = buildSupportMetrics()
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)))
    vi.stubGlobal('fetch', fetchMock)

    await expect(supportMetricsApi.getMetrics()).resolves.toEqual(payload)

    const [url, options] = fetchMock.mock.calls[0]
    expect(new URL(url).pathname).toBe('/api/dashboard/support-metrics')
    expect(new URL(url).search).toBe('')
    expect(options).toMatchObject({ method: 'GET', credentials: 'include' })
  })

  it('conserva el tratamiento global de sesión expirada del cliente HTTP', async () => {
    const { supportMetricsApi } = await import('@/api/supportMetrics.api')
    const expired = vi.fn()
    setUnauthorizedHandler(expired)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'not authenticated' }), { status: 401 }),
    ))

    await expect(supportMetricsApi.getMetrics()).rejects.toMatchObject({ status: 401 })
    expect(expired).toHaveBeenCalledTimes(1)
  })
})
