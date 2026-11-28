import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/httpClient'
import type { SupportMetrics } from '@/types/supportMetrics'
import { buildSupportMetrics } from '../helpers/supportMetricsFixtures'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

async function loadHook() {
  return (await import('@/hooks/useSupportMetrics')).useSupportMetrics
}

function deferred() {
  let resolve!: (value: SupportMetrics) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<SupportMetrics>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

describe('useSupportMetrics', () => {
  it('carga un agregado una vez sin caché global ni proveedor de consultas', async () => {
    const useSupportMetrics = await loadHook()
    const pending = deferred()
    const api = { getMetrics: vi.fn(() => pending.promise) }
    const { result } = renderHook(() => useSupportMetrics('admin-a', api))

    expect(result.current.status).toBe('loading')
    expect(result.current.data).toBeNull()
    expect(result.current.error).toBeNull()
    const payload = buildSupportMetrics({ average_resolution_minutes: null })
    await act(async () => pending.resolve(payload))

    expect(result.current.status).toBe('success')
    expect(result.current.data).toBe(payload)
    expect(result.current.data?.average_resolution_minutes).toBeNull()
    expect(api.getMetrics).toHaveBeenCalledTimes(1)
  })

  it.each([
    new ApiError(500, 'technical failure'), new TypeError('Failed to fetch'),
  ])('expone errores técnicos sin datos ficticios ni reintento automático', async (error) => {
    const useSupportMetrics = await loadHook()
    const api = { getMetrics: vi.fn().mockRejectedValue(error) }
    const { result } = renderHook(() => useSupportMetrics('admin-a', api))

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.error).toBe(error)
    expect(result.current.data).toBeNull()
    expect(result.current.canRetry).toBe(true)
    expect(api.getMetrics).toHaveBeenCalledTimes(1)
  })

  it('reintenta a petición y retira los datos previos durante carga y error', async () => {
    const useSupportMetrics = await loadHook()
    const retry = deferred()
    const error = new TypeError('Failed to fetch')
    const api = { getMetrics: vi.fn()
      .mockResolvedValueOnce(buildSupportMetrics())
      .mockRejectedValueOnce(error)
      .mockReturnValueOnce(retry.promise) }
    const { result } = renderHook(() => useSupportMetrics('admin-a', api))
    await waitFor(() => expect(result.current.status).toBe('success'))

    act(() => result.current.retry())
    expect(result.current.data).toBeNull()
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.data).toBeNull()
    act(() => result.current.retry())
    expect(result.current.status).toBe('loading')
    expect(result.current.error).toBeNull()
    const payload = buildSupportMetrics({ sla_compliance_percentage: null })
    await act(async () => retry.resolve(payload))
    expect(result.current.data).toBe(payload)
    expect(api.getMetrics).toHaveBeenCalledTimes(3)
  })

  it.each([401, 404])('retira datos y no reintenta elevación/sesión ante %s', async (status) => {
    const useSupportMetrics = await loadHook()
    const error = new ApiError(status, 'denied')
    const api = { getMetrics: vi.fn().mockRejectedValue(error) }
    const { result } = renderHook(() => useSupportMetrics('admin-a', api))

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.data).toBeNull()
    expect(result.current.error).toBe(error)
    expect(result.current.canRetry).toBe(false)
    act(() => result.current.retry())
    expect(api.getMetrics).toHaveBeenCalledTimes(1)
  })

  it('sin actor validado permanece inactivo, incluso al pedir reintento', async () => {
    const useSupportMetrics = await loadHook()
    const api = { getMetrics: vi.fn() }
    const { result } = renderHook(() => useSupportMetrics(null, api))

    expect(result.current.status).toBe('idle')
    expect(result.current.data).toBeNull()
    act(() => result.current.retry())
    expect(api.getMetrics).not.toHaveBeenCalled()
  })

  it('oculta datos desde el primer render del nuevo actor, sin esperar al efecto', async () => {
    const useSupportMetrics = await loadHook()
    const next = deferred()
    const api = { getMetrics: vi.fn().mockResolvedValueOnce(buildSupportMetrics())
      .mockReturnValueOnce(next.promise) }
    const seen: Array<{ actor: string; data: SupportMetrics | null }> = []
    const { result, rerender } = renderHook(({ actor }) => {
      const state = useSupportMetrics(actor, api)
      seen.push({ actor, data: state.data })
      return state
    }, { initialProps: { actor: 'admin-a' } })
    await waitFor(() => expect(result.current.status).toBe('success'))

    rerender({ actor: 'admin-b' })

    expect(result.current.data).toBeNull()
    expect(seen.filter(({ actor }) => actor === 'admin-b').every(({ data }) => data === null)).toBe(true)
    const payload = buildSupportMetrics({ total_tickets: 20 })
    await act(async () => next.resolve(payload))
    expect(result.current.data).toBe(payload)
  })

  it.each(['success', '401', '404', 'network'])(
    'descarta una respuesta antigua (%s) después de completar el nuevo actor', async (kind) => {
      const useSupportMetrics = await loadHook()
      const old = deferred()
      const current = buildSupportMetrics({ total_tickets: 20 })
      const api = { getMetrics: vi.fn().mockReturnValueOnce(old.promise)
        .mockResolvedValueOnce(current) }
      const { result, rerender } = renderHook(
        ({ actor }) => useSupportMetrics(actor, api),
        { initialProps: { actor: 'admin-a' } },
      )
      rerender({ actor: 'admin-b' })
      await waitFor(() => expect(result.current.data).toBe(current))

      await act(async () => {
        if (kind === 'success') old.resolve(buildSupportMetrics())
        else old.reject(kind === 'network'
          ? new TypeError('Failed to fetch') : new ApiError(Number(kind), 'old error'))
      })

      expect(result.current.status).toBe('success')
      expect(result.current.data).toBe(current)
      expect(result.current.error).toBeNull()
    },
  )

  it('desmontar cancela la petición y una respuesta tardía no puebla otro montaje', async () => {
    const useSupportMetrics = await loadHook()
    const old = deferred()
    const next = deferred()
    const api = { getMetrics: vi.fn().mockReturnValueOnce(old.promise)
      .mockReturnValueOnce(next.promise) }
    const first = renderHook(() => useSupportMetrics('admin-a', api))
    const signal = api.getMetrics.mock.calls[0][0] as AbortSignal
    first.unmount()
    expect(signal.aborted).toBe(true)
    const second = renderHook(() => useSupportMetrics('admin-a', api))

    await act(async () => old.resolve(buildSupportMetrics()))
    expect(second.result.current.status).toBe('loading')
    expect(second.result.current.data).toBeNull()
    const payload = buildSupportMetrics({ total_tickets: 30 })
    await act(async () => next.resolve(payload))
    expect(second.result.current.data).toBe(payload)
  })

  it('invalidar la sesión oculta datos y obliga a nueva lectura incluso para el mismo actor', async () => {
    const useSupportMetrics = await loadHook()
    const next = deferred()
    const api = { getMetrics: vi.fn().mockResolvedValueOnce(buildSupportMetrics())
      .mockReturnValueOnce(next.promise) }
    const { result, rerender } = renderHook(
      ({ actor }: { actor: string | null }) => useSupportMetrics(actor, api),
      { initialProps: { actor: 'admin-a' as string | null } },
    )
    await waitFor(() => expect(result.current.status).toBe('success'))
    rerender({ actor: null })
    expect(result.current.status).toBe('idle')
    expect(result.current.data).toBeNull()
    rerender({ actor: 'admin-a' })
    expect(result.current.status).toBe('loading')
    expect(result.current.data).toBeNull()
    expect(api.getMetrics).toHaveBeenCalledTimes(2)
    await act(async () => next.resolve(buildSupportMetrics()))
  })

  it('mantiene estados independientes para dos consumidores, sin reutilizar métricas', async () => {
    const useSupportMetrics = await loadHook()
    const next = deferred()
    const api = { getMetrics: vi.fn().mockResolvedValueOnce(buildSupportMetrics())
      .mockReturnValueOnce(next.promise) }
    const first = renderHook(() => useSupportMetrics('admin-a', api))
    await waitFor(() => expect(first.result.current.status).toBe('success'))

    const second = renderHook(() => useSupportMetrics('admin-a', api))
    expect(second.result.current.status).toBe('loading')
    expect(second.result.current.data).toBeNull()
    expect(api.getMetrics).toHaveBeenCalledTimes(2)
    await act(async () => next.resolve(buildSupportMetrics()))
  })

  it('no consulta por polling, foco o visibilidad', async () => {
    const useSupportMetrics = await loadHook()
    vi.useFakeTimers()
    const api = { getMetrics: vi.fn().mockResolvedValue(buildSupportMetrics()) }
    const { result } = renderHook(() => useSupportMetrics('admin-a', api))
    await act(async () => { await Promise.resolve() })
    expect(result.current.status).toBe('success')

    act(() => {
      vi.advanceTimersByTime(120_000)
      window.dispatchEvent(new Event('focus'))
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(api.getMetrics).toHaveBeenCalledTimes(1)
  })
})
