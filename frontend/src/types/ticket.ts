/** Prioridades del catálogo de HU-03. La coincidencia con el backend es exacta. */
export const PRIORITIES = ['Crítica', 'Alta', 'Media', 'Baja'] as const

export type Priority = (typeof PRIORITIES)[number]

export const DEFAULT_PRIORITY: Priority = 'Media'

/** Estados del catálogo de HU-03/HU-08. La coincidencia con el backend es exacta. */
export const STATUSES = ['Abierto', 'En progreso', 'Resuelto', 'Cerrado'] as const

export type TicketStatus = (typeof STATUSES)[number]

/** Flujo del ciclo de vida de HU-08: destinos válidos por estado actual. */
export const STATUS_TRANSITIONS: Record<TicketStatus, readonly TicketStatus[]> = {
  Abierto: ['En progreso'],
  'En progreso': ['Resuelto'],
  Resuelto: ['En progreso', 'Cerrado'],
  Cerrado: [],
}

/** Técnico responsable de un ticket (`{id, name}` o `null`). */
export interface TicketAssignee {
  id: string
  name: string
}

/** Solicitante del detalle de un ticket (HU-06). */
export interface TicketRequester {
  id: string
  name: string
  email: string
}

/** SLA calculado de un ticket (HU-05). `null` mientras no tenga prioridad. */
export interface TicketSla {
  target_minutes: number
  started_at: string
  due_at: string
  elapsed_minutes: number
  remaining_minutes: number
  status: string
  near_due: boolean
  breached: boolean
}

/** Resumen de un ticket para los listados (`GET /api/tickets`, `/all`, `/assignments/mine`). */
export interface TicketSummary {
  id: string
  title: string
  priority: string | null
  status: string
  assignee: TicketAssignee | null
  sla: TicketSla | null
  created_at: string
}

/** Ticket devuelto por la API de tickets (HU-02, HU-03 y HU-06). */
export interface Ticket {
  id: string
  title: string
  description: string
  priority: string | null
  status: string
  created_at: string
  requester_id: string
  resolved_at?: string | null
  assignee?: TicketAssignee | null
  requester?: TicketRequester | null
  sla?: TicketSla | null
}

/** El detalle usa el mismo contrato que la creación (HU-06). */
export type TicketDetail = Ticket

/** Técnico del directorio (`GET /api/technicians`). Solo identificador y nombre. */
export interface Technician {
  id: string
  name: string
}

/** Comentario de seguimiento de un ticket (HU-07). */
export interface TicketComment {
  id: string
  ticket_id: string
  body: string
  author: TicketAssignee | null
  created_at: string
}

/** Fila de GET /api/sla/policies. Solo el administrador puede consultarla. */
export interface SlaPolicy {
  priority: string
  hours: number
}
