import { request } from '@/api/httpClient'
import type { TicketDashboard } from '@/types/dashboard'

export type RequestFn = typeof request

/** Contrato HTTP del dashboard, inyectable para las pruebas. */
export function createDashboardApi(http: RequestFn = request) {
  return {
    getTickets(): Promise<TicketDashboard> {
      return http<TicketDashboard>('/api/dashboard/tickets')
    },
  }
}

export type DashboardApi = ReturnType<typeof createDashboardApi>

export const dashboardApi = createDashboardApi()
