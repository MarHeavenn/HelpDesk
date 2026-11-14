import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
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
import {
  buildSlaDashboard,
  buildTicketDashboard,
} from '../helpers/dashboardFixtures'
import type { AuthUser } from '@/types/domain'

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubDashboardFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: unknown) => {
      const url = String(input)
      if (url.includes('/api/dashboard/sla')) {
        return jsonResponse(buildSlaDashboard())
      }
      if (url.includes('/api/tickets') || url.includes('/api/technicians')) {
        return jsonResponse([])
      }
      return jsonResponse(buildTicketDashboard())
    }),
  )
}

function renderRouteWith(api: ReturnType<typeof createAuthApi>, route: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  stubDashboardFetch()

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider api={api}>
        <MemoryRouter initialEntries={[route]}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

function renderRoute(route: string, user?: AuthUser) {
  const api = user
    ? createAuthApi(user)
    : createAuthApi(ADMIN, {
        me: vi.fn(async () => {
          throw new ApiError(401, 'sin sesión')
        }),
      })

  return renderRouteWith(api, route)
}

afterEach(() => {
  vi.unstubAllGlobals()
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

  it('muestra la carga del armazón mientras valida la sesión', () => {
    renderRouteWith(
      createAuthApi(ADMIN, { me: () => new Promise<AuthUser>(() => undefined) }),
      '/',
    )

    expect(screen.getByRole('status')).toHaveTextContent('Validando sesión...')
  })

  it('muestra el error con «Reintentar» si falla la validación', async () => {
    let attempts = 0
    const me = vi.fn(async (): Promise<AuthUser> => {
      attempts += 1
      if (attempts === 1) throw new ApiError(500, 'sin conexión')
      return ADMIN
    })
    renderRouteWith(createAuthApi(ADMIN, { me }), '/')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo validar la sesión.',
    )

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
    ).toBeInTheDocument()
    expect(me).toHaveBeenCalledTimes(2)
  })

  it('conserva la sesión local ante un error de red y permite reintentar', async () => {
    localStorage.setItem('helpdesk.user', JSON.stringify(ADMIN))
    let attempts = 0
    const me = vi.fn(async (): Promise<AuthUser> => {
      attempts += 1
      if (attempts === 1) throw new ApiError(500, 'sin conexión')
      return ADMIN
    })
    renderRouteWith(createAuthApi(ADMIN, { me }), '/')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo validar la sesión.',
    )
    expect(localStorage.getItem('helpdesk.user')).not.toBeNull()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
    ).toBeInTheDocument()
  })

  it('limpia la sesión y vuelve a /login si el backend responde 401', async () => {
    localStorage.setItem('helpdesk.user', JSON.stringify(ADMIN))
    renderRouteWith(
      createAuthApi(ADMIN, {
        me: vi.fn(async (): Promise<AuthUser> => {
          throw new ApiError(401, 'sin sesión')
        }),
      }),
      '/',
    )

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Iniciar sesión' }),
    ).toBeInTheDocument()
    expect(localStorage.getItem('helpdesk.user')).toBeNull()
  })
})
