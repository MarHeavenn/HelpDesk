import { describe, expect, it, vi } from 'vitest'

import {
  createNotificationsApi,
  type RequestFn,
} from '@/api/notifications.api'

function httpMock(payload: unknown = {}): RequestFn {
  return vi.fn(async () => payload) as unknown as RequestFn
}

describe('notifications.api', () => {
  it('consulta el listado y el contador', async () => {
    const http = httpMock([])
    const api = createNotificationsApi(http)

    await api.list()
    await api.unreadCount()

    expect(http).toHaveBeenNthCalledWith(1, '/api/notifications')
    expect(http).toHaveBeenNthCalledWith(
      2,
      '/api/notifications/unread-count',
    )
  })

  it('marca una notificación codificando el identificador', async () => {
    const http = httpMock({})
    const api = createNotificationsApi(http)

    await api.markRead('a/b')

    expect(http).toHaveBeenCalledWith('/api/notifications/a%2Fb/read', {
      method: 'POST',
    })
  })

  it('marca todas como leídas', async () => {
    const http = httpMock({})
    const api = createNotificationsApi(http)

    await api.markAllRead()

    expect(http).toHaveBeenCalledWith('/api/notifications/read-all', {
      method: 'POST',
    })
  })
})
