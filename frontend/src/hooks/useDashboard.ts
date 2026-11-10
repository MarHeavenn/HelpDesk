import { useQuery } from '@tanstack/react-query'

import { dashboardApi, type DashboardApi } from '@/api/dashboard.api'

export const dashboardKeys = {
  tickets: ['dashboard', 'tickets'] as const,
  sla: (days: number) => ['dashboard', 'sla', days] as const,
}

/** Resumen agregado de tickets (RF-91). */
export function useTicketsDashboard(api: DashboardApi = dashboardApi) {
  return useQuery({
    queryKey: dashboardKeys.tickets,
    queryFn: () => api.getTickets(),
    retry: false,
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
