import { request } from '@/api/httpClient'
import type { SupportMetrics } from '@/types/supportMetrics'

/** Cliente propio: no amplía DashboardApi ni acepta filtros de otras vistas. */
export function createSupportMetricsApi(http: typeof request = request) {
  return {
    getMetrics(signal?: AbortSignal): Promise<SupportMetrics> {
      return signal
        ? http<SupportMetrics>('/api/dashboard/support-metrics', { signal })
        : http<SupportMetrics>('/api/dashboard/support-metrics')
    },
  }
}

export type SupportMetricsApi = ReturnType<typeof createSupportMetricsApi>

export const supportMetricsApi = createSupportMetricsApi()
