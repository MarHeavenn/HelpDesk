import { request } from '@/api/httpClient'
import type {
  AppNotification,
  MarkAllReadResult,
  UnreadCount,
} from '@/types/notification'

export type RequestFn = typeof request

/** Contrato HTTP del centro de notificaciones, inyectable para pruebas. */
export function createNotificationsApi(http: RequestFn = request) {
  return {
    /** Notificaciones visibles para el actor (RF-147, RF-148). */
    list(): Promise<AppNotification[]> {
      return http<AppNotification[]>('/api/notifications')
    },
    /** Notificaciones propias sin leer (RF-149). */
    unreadCount(): Promise<UnreadCount> {
      return http<UnreadCount>('/api/notifications/unread-count')
    },
    /** Marca como leída una notificación propia (RF-150). */
    markRead(notificationId: string): Promise<AppNotification> {
      return http<AppNotification>(
        `/api/notifications/${encodeURIComponent(notificationId)}/read`,
        { method: 'POST' },
      )
    },
    /** Marca como leídas todas las notificaciones propias (RF-151). */
    markAllRead(): Promise<MarkAllReadResult> {
      return http<MarkAllReadResult>('/api/notifications/read-all', {
        method: 'POST',
      })
    },
  }
}

export type NotificationsApi = ReturnType<typeof createNotificationsApi>

export const notificationsApi = createNotificationsApi()
