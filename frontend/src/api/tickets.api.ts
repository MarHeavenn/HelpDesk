import { request } from '@/api/httpClient'
import type { SlaPolicy, Ticket } from '@/types/ticket'

export type RequestFn = typeof request

export interface CreateTicketInput {
  title: string
  description: string
}

/** Contrato HTTP de alta de tickets (HU-02) y de prioridad (HU-03). */
export function createTicketsApi(http: RequestFn = request) {
  return {
    createTicket(input: CreateTicketInput): Promise<Ticket> {
      return http<Ticket>('/api/tickets', { method: 'POST', body: input })
    },
    setPriority(ticketId: string, priority: string): Promise<Ticket> {
      return http<Ticket>(
        `/api/tickets/${encodeURIComponent(ticketId)}/priority`,
        { method: 'PUT', body: { priority } },
      )
    },
    getSlaPolicies(): Promise<SlaPolicy[]> {
      return http<SlaPolicy[]>('/api/sla/policies')
    },
  }
}

export type TicketsApi = ReturnType<typeof createTicketsApi>

export const ticketsApi = createTicketsApi()
