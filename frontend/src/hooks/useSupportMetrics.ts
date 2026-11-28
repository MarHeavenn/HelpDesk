import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '@/api/httpClient'
import { supportMetricsApi, type SupportMetricsApi } from '@/api/supportMetrics.api'
import type { SupportMetrics } from '@/types/supportMetrics'

interface MetricsState {
  status: 'idle' | 'loading' | 'success' | 'error'
  data: SupportMetrics | null
  error: unknown
}

interface Snapshot extends MetricsState {
  actorKey: string | null
  api: SupportMetricsApi
  attempt: number
}

function emptyState(status: 'idle' | 'loading'): MetricsState {
  return { status, data: null, error: null }
}

/**
 * Estado local, sin caché ni polling. El llamador pasa null cuando la sesión
 * no esté validada/habilitada y una clave de actor cuando pueda consultar.
 * El cliente HTTP conserva el tratamiento global de sesión expirada.
 */
export function useSupportMetrics(
  actorKey: string | null,
  api: SupportMetricsApi = supportMetricsApi,
) {
  const [attempt, setAttempt] = useState(0)
  const [snapshot, setSnapshot] = useState<Snapshot>(() => ({
    actorKey, api, attempt,
    ...emptyState(actorKey === null ? 'idle' : 'loading'),
  }))

  // Oculta el resultado anterior durante el propio render del cambio de
  // contexto/reintento, no solo cuando se ejecute el efecto de limpieza.
  const state = snapshot.actorKey === actorKey &&
    snapshot.api === api && snapshot.attempt === attempt
    ? snapshot
    : emptyState(actorKey === null ? 'idle' : 'loading')

  useEffect(() => {
    let ignore = false
    const controller = new AbortController()
    const context = { actorKey, api, attempt }
    setSnapshot({
      ...context,
      ...emptyState(actorKey === null ? 'idle' : 'loading'),
    })

    async function load() {
      try {
        const data = await api.getMetrics(controller.signal)
        if (!ignore) {
          setSnapshot({ ...context, status: 'success', data, error: null })
        }
      } catch (error) {
        if (!ignore) {
          setSnapshot({ ...context, status: 'error', data: null, error })
        }
      }
    }

    if (actorKey !== null) void load()
    return () => {
      ignore = true
      controller.abort()
    }
  }, [actorKey, api, attempt])

  const protectedFailure = state.error instanceof ApiError &&
    (state.error.status === 401 || state.error.status === 404)
  const retry = useCallback(() => {
    if (actorKey !== null && !protectedFailure) {
      setAttempt((previous) => previous + 1)
    }
  }, [actorKey, protectedFailure])

  return {
    status: state.status,
    data: state.data,
    error: state.error,
    canRetry: state.status === 'error' && !protectedFailure,
    retry,
  }
}
