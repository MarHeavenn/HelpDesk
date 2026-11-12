/** Cobertura RF-78: marcadores sin datos ni acciones simuladas. */
import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import PlaceholderPage from '@/pages/PlaceholderPage'
import { ADMIN, CLIENTE, renderApp } from '../helpers/renderApp'

describe('PlaceholderPage', () => {
  it('muestra el título, «Próximamente» y el enlace de salida', async () => {
    renderApp(<PlaceholderPage title="Técnicos" />, { user: ADMIN })

    expect(
      screen.getByRole('heading', { level: 1, name: 'Técnicos' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: 'Próximamente' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Esta sección estará disponible en una próxima entrega.'),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(
        screen.getByRole('link', { name: 'Volver al inicio' }),
      ).toHaveAttribute('href', '/'),
    )
  })

  it('no inventa datos ni acciones de la sección pendiente', async () => {
    renderApp(<PlaceholderPage title="Notificaciones" />, { user: ADMIN })
    await screen.findByText('Próximamente')

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('lleva al cliente a su primera ruta permitida', async () => {
    renderApp(<PlaceholderPage title="Notificaciones" />, { user: CLIENTE })

    await waitFor(() =>
      expect(
        screen.getByRole('link', { name: 'Volver al inicio' }),
      ).toHaveAttribute('href', '/mis-tickets'),
    )
  })
})
