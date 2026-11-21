import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'

import NotificationBell from '@/components/notifications/NotificationBell'
import { createNotificationsApi } from '../helpers/notificationFixtures'
import { renderApp } from '../helpers/renderApp'

describe('NotificationBell', () => {
  it('no muestra insignia cuando no hay notificaciones sin leer', async () => {
    const api = createNotificationsApi({
      unreadCount: vi.fn(async () => ({ count: 0 })),
    })

    renderApp(<NotificationBell api={api} />)

    const link = await screen.findByRole('link', { name: 'Notificaciones' })
    expect(link).toHaveAttribute('href', '/notificaciones')
    expect(within(link).queryByTestId('notification-badge')).not.toBeInTheDocument()
  })

  it('muestra el contador y lo anuncia en la etiqueta accesible', async () => {
    const api = createNotificationsApi({
      unreadCount: vi.fn(async () => ({ count: 3 })),
    })

    renderApp(<NotificationBell api={api} />)

    const link = await screen.findByRole('link', {
      name: 'Notificaciones, 3 sin leer',
    })
    expect(within(link).getByTestId('notification-badge')).toHaveTextContent('3')
  })

  it('limita la insignia a 9+', async () => {
    const api = createNotificationsApi({
      unreadCount: vi.fn(async () => ({ count: 12 })),
    })

    renderApp(<NotificationBell api={api} />)

    const link = await screen.findByRole('link', {
      name: 'Notificaciones, 12 sin leer',
    })
    expect(within(link).getByTestId('notification-badge')).toHaveTextContent(
      '9+',
    )
  })
})
