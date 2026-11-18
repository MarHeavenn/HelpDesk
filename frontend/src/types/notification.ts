/** Contrato de notificaciones internas de ticket (HU-15). */

export type NotificationType =
  | 'ticket_assigned'
  | 'ticket_reassigned'
  | 'ticket_status_changed'
  | 'ticket_resolved'
  | 'ticket_reopened'
  | 'sla_near_due'
  | 'sla_breached'

/** Usuario visible en una notificación: solo identificador y nombre. */
export interface NotificationUser {
  id: string
  name: string | null
}

/** Ticket referenciado por una notificación: solo identificador y título. */
export interface NotificationTicket {
  id: string
  title: string
}

/** Notificación dirigida a un usuario (RF-146). */
export interface AppNotification {
  id: string
  type: NotificationType
  ticket: NotificationTicket
  recipient: NotificationUser
  actor: NotificationUser
  previous_value: string | null
  new_value: string | null
  created_at: string
  read_at: string | null
}

/** Contador de notificaciones propias sin leer (RF-149). */
export interface UnreadCount {
  count: number
}

/** Resultado de marcar todas como leídas (RF-151). */
export interface MarkAllReadResult {
  updated: number
}
