import { request } from '@/api/httpClient'
import type { SlaDashboard, TicketDashboard } from '@/types/dashboard'
import type { TicketSummary } from '@/types/ticket'

export type RequestFn = typeof request

/** Contrato HTTP del dashboard, inyectable para las pruebas. */
export function createDashboardApi(http: RequestFn = request) {
  return {
    getTickets(): Promise<TicketDashboard> {
      return http<TicketDashboard>('/api/dashboard/tickets')
    },
    getSla(days: number): Promise<SlaDashboard> {
      return http<SlaDashboard>(`/api/dashboard/sla?days=${days}`)
    },
    /** Tickets activos con SLA en riesgo o incumplido (HU-10). */
    getAttention(): Promise<TicketSummary[]> {
      return http<TicketSummary[]>('/api/tickets/requiring-attention')
    },
  }
}

export type DashboardApi = ReturnType<typeof createDashboardApi>

export const dashboardApi = createDashboardApi()
