import { useQuery } from '@tanstack/react-query'

import { dashboardApi, type DashboardApi } from '@/api/dashboard.api'

export const dashboardKeys = {
  tickets: ['dashboard', 'tickets'] as const,
  sla: (days: number) => ['dashboard', 'sla', days] as const,
  attention: ['dashboard', 'attention'] as const,
}

/** Resumen agregado de tickets (RF-91). */
export function useTicketsDashboard(api: DashboardApi = dashboardApi) {
  return useQuery({
    queryKey: dashboardKeys.tickets,
    queryFn: () => api.getTickets(),
    retry: false,
  })
}

/** Tickets que requieren atención por SLA (RF-126). */
export function useAttentionAlerts(
  api: DashboardApi = dashboardApi,
  enabled = true,
) {
  return useQuery({
    queryKey: dashboardKeys.attention,
    queryFn: () => api.getAttention(),
    retry: false,
    enabled,
  })
}

/** Cumplimiento de SLA para el periodo indicado (RF-102). */
export function useSlaDashboard(days: number, api: DashboardApi = dashboardApi) {
  return useQuery({
    queryKey: dashboardKeys.sla(days),
    queryFn: () => api.getSla(days),
    retry: false,
  })
}
