/** Prioridades del catálogo de HU-03. La coincidencia con el backend es exacta. */
export const PRIORITIES = ['Crítica', 'Alta', 'Media', 'Baja'] as const

export type Priority = (typeof PRIORITIES)[number]

export const DEFAULT_PRIORITY: Priority = 'Media'

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
}

/** Fila de GET /api/sla/policies. Solo el administrador puede consultarla. */
export interface SlaPolicy {
  priority: string
  hours: number
}
