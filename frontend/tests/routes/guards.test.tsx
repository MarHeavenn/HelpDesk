import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { ApiError } from '@/api/httpClient'
import { AuthProvider } from '@/context/AuthContext'
import AppRoutes from '@/routes'
import {
  ADMIN,
  CLIENTE,
  TECNICO,
  createAuthApi,
} from '../helpers/renderApp'
import type { AuthUser } from '@/types/domain'

function renderRoute(route: string, user?: AuthUser) {
  const api = user
    ? createAuthApi(user)
    : createAuthApi(ADMIN, {
        me: vi.fn(async () => {
          throw new ApiError(401, 'sin sesión')
        }),
      })

  return render(
    <AuthProvider api={api}>
      <MemoryRouter initialEntries={[route]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  )
}

afterEach(() => {
  localStorage.clear()
})

describe('rutas y guards', () => {
  it('redirige a /login a un visitante sin sesión', async () => {
    renderRoute('/tickets')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Iniciar sesión' }),
    ).toBeInTheDocument()
  })

  it('redirige a /login aunque la ruta no exista', async () => {
    renderRoute('/ruta-inexistente')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Iniciar sesión' }),
    ).toBeInTheDocument()
  })

  it('lleva al administrador autenticado de /login a su primera ruta', async () => {
    renderRoute('/login', ADMIN)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
    ).toBeInTheDocument()
  })

  it('lleva al cliente autenticado de /login a /mis-tickets', async () => {
    renderRoute('/login', CLIENTE)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Mis tickets' }),
    ).toBeInTheDocument()
  })

  it('redirige /cuenta a /cuenta/perfil', async () => {
    renderRoute('/cuenta', ADMIN)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Mi perfil' }),
    ).toBeInTheDocument()
  })

  it('muestra el aviso y la ruta permitida si el rol no puede entrar', async () => {
    renderRoute('/tecnicos', TECNICO)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para acceder a esta sección',
    )
  })

  it('redirige al cliente de / a /mis-tickets', async () => {
    renderRoute('/', CLIENTE)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Mis tickets' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para acceder a esta sección',
    )
  })

  it('muestra la 404 con enlace de salida en una ruta desconocida', async () => {
    renderRoute('/ruta-inexistente', ADMIN)

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Página no encontrada',
      }),
    ).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole('link', { name: 'Volver al inicio' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
    ).toBeInTheDocument()
  })

  it.each([
    ['/tickets', 'Todos los tickets'],
    ['/mis-tickets', 'Mis tickets'],
    ['/tickets/nuevo', 'Crear ticket'],
    ['/tecnicos', 'Técnicos'],
    ['/sla', 'SLA'],
    ['/usuarios', 'Usuarios'],
    ['/empresas', 'Empresas'],
    ['/notificaciones', 'Notificaciones'],
    ['/cuenta/perfil', 'Mi perfil'],
  ])('renderiza la ruta %s', async (route, title) => {
    renderRoute(route, ADMIN)

    expect(
      await screen.findByRole('heading', { level: 1, name: title }),
    ).toBeInTheDocument()
  })
})
