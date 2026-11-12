/** Cobertura RF-76: identidad real en el perfil y cierre de sesión. */
import { afterEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import ProfilePage from '@/pages/ProfilePage'
import { ADMIN, CLIENTE, createAuthApi, renderApp } from '../helpers/renderApp'

afterEach(() => {
  localStorage.clear()
})

describe('ProfilePage', () => {
  it('muestra el nombre, el correo y el rol de la sesión', async () => {
    renderApp(<ProfilePage />, { user: ADMIN })

    expect(await screen.findByText('Ana Admin')).toBeInTheDocument()
    expect(screen.getByText('admin@helpdesk.dev')).toBeInTheDocument()
    expect(screen.getByText('Administrador')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Mi perfil' }),
    ).toBeInTheDocument()
  })

  it('usa el correo como respaldo si la sesión no trae nombre', async () => {
    const unnamed = { ...CLIENTE, name: '' }
    renderApp(<ProfilePage />, { user: unnamed })

    expect(
      (await screen.findAllByText('carla@example.com')).length,
    ).toBeGreaterThan(0)
    expect(screen.getByText('Cliente')).toBeInTheDocument()
  })

  it('cierra la sesión real y vuelve a /login', async () => {
    const api = createAuthApi(ADMIN)
    renderApp(<ProfilePage />, { api })
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Cerrar sesión' }))

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
    expect(api.logout).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('helpdesk.user')).toBeNull()
  })
})
