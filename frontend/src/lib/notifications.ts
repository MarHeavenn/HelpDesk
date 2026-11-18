import { formatTicketDate } from '@/lib/dates'
import { strings } from '@/lib/strings'
import type { AppNotification, NotificationType } from '@/types/notification'

/** Clave de icono que usa la lista y la tarjeta del dashboard. */
export type NotificationIcon =
  | 'assigned'
  | 'reassigned'
  | 'status'
  | 'resolved'
  | 'reopened'
  | 'slaNearDue'
  | 'slaBreached'

const ICONS: Record<NotificationType, NotificationIcon> = {
  ticket_assigned: 'assigned',
  ticket_reassigned: 'reassigned',
  ticket_status_changed: 'status',
  ticket_resolved: 'resolved',
  ticket_reopened: 'reopened',
  sla_near_due: 'slaNearDue',
  sla_breached: 'slaBreached',
}

/** Icono asociado al tipo de notificación. */
export function notificationIcon(type: NotificationType): NotificationIcon {
  return ICONS[type] ?? 'status'
}

/** Etiqueta corta del tipo de notificación. */
export function notificationTypeLabel(type: NotificationType): string {
  return strings.notifications.types[type] ?? strings.notifications.title
}

/** Mensaje en español para una notificación (RF-152). */
export function notificationMessage(notification: AppNotification): string {
  if (notification.type === 'ticket_status_changed') {
    return strings.notifications.messages.ticket_status_changed(
      notification.previous_value,
      notification.new_value,
    )
  }
  if (notification.type === 'ticket_assigned') {
    return strings.notifications.messages.ticket_assigned(
      notification.new_value,
    )
  }
  if (notification.type === 'ticket_reassigned') {
    return strings.notifications.messages.ticket_reassigned(
      notification.new_value,
    )
  }
  if (notification.type === 'ticket_resolved') {
    return strings.notifications.messages.ticket_resolved()
  }
  if (notification.type === 'ticket_reopened') {
    return strings.notifications.messages.ticket_reopened()
  }
  if (notification.type === 'sla_near_due') {
    return strings.notifications.messages.sla_near_due(
      notification.new_value
        ? formatTicketDate(notification.new_value)
        : null,
    )
  }
  if (notification.type === 'sla_breached') {
    return strings.notifications.messages.sla_breached(
      notification.new_value
        ? formatTicketDate(notification.new_value)
        : null,
    )
  }
  return strings.notifications.title
}
