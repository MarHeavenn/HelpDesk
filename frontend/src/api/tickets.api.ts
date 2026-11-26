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

/**
 * Contrato HTTP de tickets: listados, detalle, acciones, técnicos y comentarios.
 * Los listados conservan el resumen recibido, incluido requester mínimo/nulo/ausente,
 * sin completar filas mediante consultas de detalle o directorio.
 */
export function createTicketsApi(http: RequestFn = request) {
  return {
    createTicket(input: CreateTicketInput): Promise<Ticket> {
      return http<Ticket>('/api/tickets', { method: 'POST', body: input })
    },
    /** Tickets visibles para el actor autenticado según su alcance (HU-13). */
    listMine(): Promise<TicketSummary[]> {
      return http<TicketSummary[]>('/api/tickets')
    },
    /** Tickets asignados al técnico autenticado (HU-04, RF-36). */
    listAssigned(): Promise<TicketSummary[]> {
      return http<TicketSummary[]>('/api/assignments/mine')
    },
    /** Tickets de la empresa; administrador, supervisor y técnico (HU-17, RF-177). */
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
