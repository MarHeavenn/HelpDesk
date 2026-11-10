import { useQuery } from '@tanstack/react-query'

import { dashboardApi, type DashboardApi } from '@/api/dashboard.api'

export const dashboardKeys = {
  tickets: ['dashboard', 'tickets'] as const,
}

/** Resumen agregado de tickets (RF-91). */
export function useTicketsDashboard(api: DashboardApi = dashboardApi) {
  return useQuery({
    queryKey: dashboardKeys.tickets,
    queryFn: () => api.getTickets(),
    retry: false,
  })
}
