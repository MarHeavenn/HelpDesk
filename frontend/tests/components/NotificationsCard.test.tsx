import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import NotificationsCard from '@/components/dashboard/NotificationsCard'
import {
  buildNotification,
  createNotificationsApi,
} from '../helpers/notificationFixtures'
import { renderApp } from '../helpers/renderApp'

describe('NotificationsCard', () => {
  it('muestra las cinco novedades más recientes y el enlace al centro', async () => {
    const notifications = Array.from({ length: 6 }, (_, index) =>
      buildNotification({
        id: `notification-${index}`,
        ticket: { id: `ticket-${index}`, title: `Ticket ${index}` },
      }),
    )
    const api = createNotificationsApi({
      list: vi.fn(async () => notifications),
    })

    renderApp(<NotificationsCard api={api} />)

    const card = await screen.findByRole('region', { name: 'Novedades' })
    const items = await within(card).findAllByRole('listitem')
    expect(items).toHaveLength(5)
    expect(within(card).queryByText('Ticket 5')).not.toBeInTheDocument()
    expect(within(card).getByRole('link', { name: 'Ver todas' })).toHaveAttribute(
      'href',
      '/notificaciones',
    )
  })

  it('muestra el estado vacío', async () => {
    const api = createNotificationsApi({
      list: vi.fn(async () => []),
    })

    renderApp(<NotificationsCard api={api} />)

    expect(
      await screen.findByText('No tienes novedades recientes.'),
    ).toBeInTheDocument()
  })

  it('muestra las alertas de SLA en las novedades', async () => {
    const api = createNotificationsApi({
      list: vi.fn(async () => [
        buildNotification({
          type: 'sla_near_due',
          new_value: '2026-11-17T13:00:00+00:00',
          actor: { id: 'system', name: 'Sistema' },
        }),
      ]),
    })

    renderApp(<NotificationsCard api={api} />)

    expect(await screen.findByText(/SLA por vencer/)).toBeInTheDocument()
  })

  it('muestra el error y reintenta', async () => {
    const list = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce([buildNotification()])
    const api = createNotificationsApi({ list })
    const user = userEvent.setup()

    renderApp(<NotificationsCard api={api} />)

    const card = await screen.findByRole('region', { name: 'Novedades' })
    expect(
      await within(card).findByText('No se pudieron cargar las novedades.'),
    ).toBeInTheDocument()

    await user.click(within(card).getByRole('button', { name: 'Reintentar' }))

    expect(
      await within(card).findByText('Ticket asignado a Tomás Técnico'),
    ).toBeInTheDocument()
    expect(list).toHaveBeenCalledTimes(2)
  })
})
