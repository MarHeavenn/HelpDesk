import { request } from '@/api/httpClient'
import type {
  SlaPolicy,
  Ticket,
  TicketComment,
  TicketDetail,
  TicketSummary,
  Technician,
} from '@/types/ticket'

export type RequestFn = typeof request

export interface CreateTicketInput {
  title: string
  description: string
}

function ticketPath(ticketId: string): string {
  return `/api/tickets/${encodeURIComponent(ticketId)}`
}

/** Contrato HTTP de tickets: listados, detalle, acciones, técnicos y comentarios. */
export function createTicketsApi(http: RequestFn = request) {
  return {
    createTicket(input: CreateTicketInput): Promise<Ticket> {
      return http<Ticket>('/api/tickets', { method: 'POST', body: input })
    },
    /** Tickets creados por el usuario autenticado (HU-02, RF-15). */
    listMine(): Promise<TicketSummary[]> {
      return http<TicketSummary[]>('/api/tickets')
    },
    /** Tickets asignados al técnico autenticado (HU-04, RF-36). */
    listAssigned(): Promise<TicketSummary[]> {
      return http<TicketSummary[]>('/api/assignments/mine')
    },
    /** Todos los tickets; solo administrador y técnico (HU-23, RF-122). */
    listAll(): Promise<TicketSummary[]> {
      return http<TicketSummary[]>('/api/tickets/all')
    },
    /** Detalle visible para el actor (HU-02 y HU-06). */
    getTicket(ticketId: string): Promise<TicketDetail> {
      return http<TicketDetail>(ticketPath(ticketId))
    },
    setPriority(ticketId: string, priority: string): Promise<Ticket> {
      return http<Ticket>(`${ticketPath(ticketId)}/priority`, {
        method: 'PUT',
        body: { priority },
      })
    },
    setStatus(ticketId: string, status: string): Promise<Ticket> {
      return http<Ticket>(`${ticketPath(ticketId)}/status`, {
        method: 'PUT',
        body: { status },
      })
    },
    assign(ticketId: string, assigneeId: string): Promise<Ticket> {
      return http<Ticket>(`${ticketPath(ticketId)}/assignee`, {
        method: 'PUT',
        body: { assignee_id: assigneeId },
      })
    },
    /** Directorio de técnicos; solo el administrador (RF-31). */
    listTechnicians(): Promise<Technician[]> {
      return http<Technician[]>('/api/technicians')
    },
    listComments(ticketId: string): Promise<TicketComment[]> {
      return http<TicketComment[]>(`${ticketPath(ticketId)}/comments`)
    },
    addComment(ticketId: string, body: string): Promise<TicketComment> {
      return http<TicketComment>(`${ticketPath(ticketId)}/comments`, {
        method: 'POST',
        body: { body },
      })
    },
    getSlaPolicies(): Promise<SlaPolicy[]> {
      return http<SlaPolicy[]>('/api/sla/policies')
    },
  }
}

export type TicketsApi = ReturnType<typeof createTicketsApi>

export const ticketsApi = createTicketsApi()
