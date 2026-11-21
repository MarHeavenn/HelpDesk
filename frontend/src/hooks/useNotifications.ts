import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  notificationsApi,
  type NotificationsApi,
} from '@/api/notifications.api'

export const notificationKeys = {
  all: ['notifications'] as const,
  list: ['notifications', 'list'] as const,
  unread: ['notifications', 'unread'] as const,
}

const REFETCH_INTERVAL_MS = 30_000

/** Notificaciones visibles para el actor, con sondeo ligero (RF-152). */
export function useNotifications(api: NotificationsApi = notificationsApi) {
  return useQuery({
    queryKey: notificationKeys.list,
    queryFn: () => api.list(),
    retry: false,
    refetchInterval: REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

/** Contador de notificaciones propias sin leer (RF-149, RF-152). */
export function useUnreadCount(api: NotificationsApi = notificationsApi) {
  return useQuery({
    queryKey: notificationKeys.unread,
    queryFn: () => api.unreadCount(),
    retry: false,
    refetchInterval: REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

/** Marca una notificación propia como leída e invalida listado y contador. */
export function useMarkNotificationRead(
  api: NotificationsApi = notificationsApi,
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (notificationId: string) => api.markRead(notificationId),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
  })
}

/** Marca todas las notificaciones propias como leídas (RF-151). */
export function useMarkAllNotificationsRead(
  api: NotificationsApi = notificationsApi,
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.markAllRead(),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
  })
}
