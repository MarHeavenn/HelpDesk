import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  notificationKeys,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from '@/hooks/useNotifications'
import {
  buildNotification,
  createNotificationsApi,
} from '../helpers/notificationFixtures'

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

function createClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
}

describe('useNotifications', () => {
  it('devuelve el listado y el contador', async () => {
    const notifications = [buildNotification()]
    const api = createNotificationsApi({
      list: vi.fn(async () => notifications),
      unreadCount: vi.fn(async () => ({ count: 1 })),
    })
    const client = createClient()

    const { result } = renderHook(
      () => ({
        list: useNotifications(api),
        unread: useUnreadCount(api),
      }),
      { wrapper: wrapper(client) },
    )

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))
    await waitFor(() => expect(result.current.unread.isSuccess).toBe(true))
    expect(result.current.list.data).toEqual(notifications)
    expect(result.current.unread.data).toEqual({ count: 1 })
  })

  it('expone el error de red sin reintentos', async () => {
    const list = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    const api = createNotificationsApi({ list })

    const { result } = renderHook(() => useNotifications(api), {
      wrapper: wrapper(createClient()),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(list).toHaveBeenCalledTimes(1)
  })

  it('refresca el listado cada 30 s y al recuperar el foco', async () => {
    const list = vi.fn(async () => [buildNotification()])
    const api = createNotificationsApi({ list })
    const client = createClient()

    const { result } = renderHook(() => useNotifications(api), {
      wrapper: wrapper(client),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const query = client.getQueryCache().find({
      queryKey: notificationKeys.list,
    })
    const options = query?.options as
      | { refetchInterval?: number | false; refetchOnWindowFocus?: boolean }
      | undefined
    expect(options?.refetchInterval).toBe(30_000)
    expect(options?.refetchOnWindowFocus).toBe(true)

    window.dispatchEvent(new Event('visibilitychange'))

    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  })

  it('invalida el listado y el contador al marcar una notificación', async () => {
    const list = vi.fn(async () => [buildNotification()])
    const unreadCount = vi.fn(async () => ({ count: 1 }))
    const markRead = vi.fn(async (notificationId: string) =>
      buildNotification({ id: notificationId, read_at: '2026-11-17T12:05:00Z' }),
    )
    const api = createNotificationsApi({ list, unreadCount, markRead })

    const { result } = renderHook(
      () => ({
        list: useNotifications(api),
        unread: useUnreadCount(api),
        markRead: useMarkNotificationRead(api),
      }),
      { wrapper: wrapper(createClient()) },
    )

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))
    await waitFor(() => expect(result.current.unread.isSuccess).toBe(true))

    act(() => result.current.markRead.mutate('notification-1'))

    await waitFor(() => expect(markRead).toHaveBeenCalledWith('notification-1'))
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(unreadCount).toHaveBeenCalledTimes(2))
  })

  it('invalida el listado al marcar todas como leídas', async () => {
    const list = vi.fn(async () => [buildNotification()])
    const markAllRead = vi.fn(async () => ({ updated: 1 }))
    const api = createNotificationsApi({ list, markAllRead })

    const { result } = renderHook(
      () => ({
        list: useNotifications(api),
        markAllRead: useMarkAllNotificationsRead(api),
      }),
      { wrapper: wrapper(createClient()) },
    )

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))

    act(() => result.current.markAllRead.mutate())

    await waitFor(() => expect(markAllRead).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  })
})
