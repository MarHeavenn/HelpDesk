import { vi } from 'vitest'

import type { NotificationsApi } from '@/api/notifications.api'
import type { AppNotification } from '@/types/notification'

export function buildNotification(
  overrides: Partial<AppNotification> = {},
): AppNotification {
  return {
    id: 'notification-1',
    type: 'ticket_assigned',
    ticket: { id: 'ticket-1', title: 'No puedo entrar' },
    recipient: { id: 'u-client', name: 'Carla Cliente' },
    actor: { id: 'u-admin', name: 'Ana Admin' },
    previous_value: null,
    new_value: 'Tomás Técnico',
    created_at: '2026-11-17T12:00:00+00:00',
    read_at: null,
    ...overrides,
  }
}

export function createNotificationsApi(
  overrides: Partial<NotificationsApi> = {},
): NotificationsApi {
  return {
    list: vi.fn(async () => [buildNotification()]),
    unreadCount: vi.fn(async () => ({ count: 1 })),
    markRead: vi.fn(async (notificationId: string) =>
      buildNotification({
        id: notificationId,
        read_at: '2026-11-17T12:05:00+00:00',
      }),
    ),
    markAllRead: vi.fn(async () => ({ updated: 1 })),
    ...overrides,
  }
}
