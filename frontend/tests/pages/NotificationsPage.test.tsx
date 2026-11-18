import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ApiError } from '@/api/httpClient'
import NotificationsPage from '@/pages/NotificationsPage'
import {
  buildNotification,
  createNotificationsApi,
} from '../helpers/notificationFixtures'
import { ADMIN, createAuthApi, renderApp } from '../helpers/renderApp'

describe('NotificationsPage', () => {
  it('muestra el listado con mensaje, ticket, actor y destinatario', async () => {
    const api = createNotificationsApi()

    renderApp(<NotificationsPage api={api} />, { user: ADMIN })

    const list = await screen.findByRole('list', {
      name: 'Listado de notificaciones',
    })
    expect(
      within(list).getByText('Ticket asignado a Tomás Técnico'),
    ).toBeInTheDocument()
    expect(within(list).getByText(/No puedo entrar/)).toBeInTheDocument()
    expect(within(list).getByText(/Carla Cliente/)).toBeInTheDocument()
    expect(
      within(list).getByRole('button', { name: 'Marcar como leída' }),
    ).toBeInTheDocument()
  })

  it('marca una notificación como leída', async () => {
    const markRead = vi.fn(async (notificationId: string) =>
      buildNotification({
        id: notificationId,
        read_at: '2026-11-17T12:05:00+00:00',
      }),
    )
    const api = createNotificationsApi({ markRead })
    const user = userEvent.setup()

    renderApp(<NotificationsPage api={api} />, { user: ADMIN })

    await user.click(
      await screen.findByRole('button', { name: 'Marcar como leída' }),
    )

    await waitFor(() =>
      expect(markRead).toHaveBeenCalledWith('notification-1'),
    )
  })

  it('marca todas las notificaciones como leídas', async () => {
    const markAllRead = vi.fn(async () => ({ updated: 1 }))
    const api = createNotificationsApi({ markAllRead })
    const user = userEvent.setup()

    renderApp(<NotificationsPage api={api} />, { user: ADMIN })

    await user.click(
      await screen.findByRole('button', {
        name: 'Marcar todas como leídas',
      }),
    )

    await waitFor(() => expect(markAllRead).toHaveBeenCalledTimes(1))
  })

  it('filtra las no leídas sin ocultar el resto al volver a todas', async () => {
    const notifications = [
      buildNotification({ id: 'unread' }),
      buildNotification({
        id: 'read',
        type: 'ticket_resolved',
        read_at: '2026-11-17T12:05:00+00:00',
      }),
    ]
    const api = createNotificationsApi({
      list: vi.fn(async () => notifications),
    })
    const user = userEvent.setup()

    renderApp(<NotificationsPage api={api} />, { user: ADMIN })

    expect(
      await screen.findByText('Ticket asignado a Tomás Técnico'),
    ).toBeInTheDocument()
    expect(screen.getByText('Ticket resuelto')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'No leídas' }))

    expect(screen.queryByText('Ticket resuelto')).not.toBeInTheDocument()
    expect(
      screen.getByText('Ticket asignado a Tomás Técnico'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Todas' }))

    expect(screen.getByText('Ticket resuelto')).toBeInTheDocument()
  })

  it('muestra el estado vacío y el vacío por filtro', async () => {
    const emptyApi = createNotificationsApi({
      list: vi.fn(async () => []),
      unreadCount: vi.fn(async () => ({ count: 0 })),
    })
    const user = userEvent.setup()

    const { unmount } = renderApp(<NotificationsPage api={emptyApi} />, {
      user: ADMIN,
    })

    expect(
      await screen.findByText('Aún no tienes notificaciones'),
    ).toBeInTheDocument()
    unmount()

    const readApi = createNotificationsApi({
      list: vi.fn(async () => [
        buildNotification({ read_at: '2026-11-17T12:05:00+00:00' }),
      ]),
      unreadCount: vi.fn(async () => ({ count: 0 })),
    })
    renderApp(<NotificationsPage api={readApi} />, { user: ADMIN })

    await screen.findByText('Ticket asignado a Tomás Técnico')
    await user.click(screen.getByRole('button', { name: 'No leídas' }))

    expect(
      screen.getByText('No tienes notificaciones sin leer'),
    ).toBeInTheDocument()
  })

  it('muestra el error y reintenta la consulta', async () => {
    const list = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce([buildNotification()])
    const api = createNotificationsApi({ list })
    const user = userEvent.setup()

    renderApp(<NotificationsPage api={api} />, { user: ADMIN })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No se pudieron cargar las notificaciones')

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(
      await screen.findByText('Ticket asignado a Tomás Técnico'),
    ).toBeInTheDocument()
    expect(list).toHaveBeenCalledTimes(2)
  })

  it('muestra una alerta de SLA con el actor Sistema', async () => {
    const api = createNotificationsApi({
      list: vi.fn(async () => [
        buildNotification({
          type: 'sla_breached',
          new_value: '2026-11-17T13:00:00+00:00',
          actor: { id: 'system', name: 'Sistema' },
        }),
      ]),
    })

    renderApp(<NotificationsPage api={api} />, { user: ADMIN })

    expect(
      await screen.findByText(/SLA incumplido: venció/),
    ).toBeInTheDocument()
    expect(screen.getByText(/por Sistema/)).toBeInTheDocument()
  })

  it('cierra la sesión cuando la consulta responde 401', async () => {
    const api = createNotificationsApi({
      list: vi.fn(async () => {
        throw new ApiError(401, 'not authenticated')
      }),
      unreadCount: vi.fn(async () => ({ count: 0 })),
    })
    const logout = vi.fn(async () => undefined)

    renderApp(<NotificationsPage api={api} />, {
      user: ADMIN,
      api: createAuthApi(ADMIN, { logout }),
    })

    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1))
    expect(
      screen.queryByText('No se pudieron cargar las notificaciones'),
    ).not.toBeInTheDocument()
  })
})
