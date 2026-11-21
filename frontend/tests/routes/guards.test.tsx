import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom'

import { ApiError } from '@/api/httpClient'
import { AuthProvider } from '@/context/AuthContext'
import AppRoutes, { RequireAuth, RequireRoutePermission } from '@/routes'
import {
  ADMIN,
  CLIENTE,
  SUPERVISOR,
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

function notFoundResponse(detail = 'company not found'): Response {
  return new Response(JSON.stringify({ detail }), {
    status: 404,
    headers: { 'Content-Type': 'application/json' },
  })
}

let fetchMock: ReturnType<typeof vi.fn> | null = null

function stubDashboardFetch(): void {
  const mock = vi.fn(async (input: unknown) => {
    const url = String(input)
    if (url.includes('/api/companies/me')) {
      return notFoundResponse()
    }
    if (url.includes('/api/companies') || url.includes('/api/users/unassigned')) {
      return jsonResponse([])
    }
    if (url.includes('/api/technicians')) {
      return jsonResponse([])
    }
    if (url.includes('/api/dashboard/sla')) {
      return jsonResponse(buildSlaDashboard())
    }
    if (url.includes('/api/notifications/unread-count')) {
      return jsonResponse({ count: 0 })
    }
    if (url.includes('/api/notifications')) {
      return jsonResponse([])
    }
    if (url.includes('/api/tickets') || url.includes('/api/technicians')) {
      return jsonResponse([])
    }
    return jsonResponse(buildTicketDashboard())
  })
  fetchMock = mock
  vi.stubGlobal('fetch', mock)
}

/** Rutas de empresas pedidas por la vista, si alguna. */
function companyRequests(): string[] {
  const calls = (fetchMock?.mock.calls ?? []) as unknown[][]
  return calls
    .map((call) => String(call[0]))
    .filter((url) => url.includes('/api/companies') || url.includes('/api/users/unassigned'))
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
  fetchMock = null
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

  it('permite al supervisor acceder al directorio existente', async () => {
    renderRoute('/tecnicos', SUPERVISOR)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Técnicos' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Aún no hay técnicos')).toBeInTheDocument()
  })

  it.each(['/mis-tickets', '/tickets/nuevo', '/sla', '/usuarios', '/empresas'])(
    'redirige al supervisor fuera de la ruta permitida %s',
    async (route) => {
      renderRoute(route, SUPERVISOR)

      expect(
        await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
      ).toBeInTheDocument()
      expect(await screen.findByRole('alert')).toHaveTextContent(
        'No tienes permiso para acceder a esta sección',
      )
    },
  )

  it('redirige al técnico de /empresas a / sin renderizar datos de empresa', async () => {
    renderRoute('/empresas', TECNICO)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para acceder a esta sección',
    )
    expect(
      screen.queryByRole('heading', { name: 'Ficha de la empresa' }),
    ).not.toBeInTheDocument()
    expect(companyRequests()).toHaveLength(0)
  })

  it('redirige al cliente de /empresas a /mis-tickets sin renderizar datos de empresa', async () => {
    renderRoute('/empresas', CLIENTE)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Mis tickets' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Ficha de la empresa' }),
    ).not.toBeInTheDocument()
    expect(companyRequests()).toHaveLength(0)
  })

  it('no consulta empresas cuando el supervisor entra en /empresas', async () => {
    renderRoute('/empresas', SUPERVISOR)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
    ).toBeInTheDocument()
    expect(companyRequests()).toHaveLength(0)
  })

  it('no permite al técnico acceder al alta de tickets', async () => {
    renderRoute('/tickets/nuevo', TECNICO)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Dashboard' }),
    ).toBeInTheDocument()
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

  it('redirige /empresas sustituyendo la entrada del historial (replace)', async () => {
    window.history.pushState({}, '', '/empresas')
    const before = window.history.length

    const api = createAuthApi(TECNICO)
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider api={api}>
          <BrowserRouter>
            <Routes>
              <Route element={<RequireAuth />}>
                <Route element={<RequireRoutePermission />}>
                  <Route path="/empresas" element={<div>Empresas</div>} />
                  <Route path="/" element={<div>Dashboard</div>} />
                </Route>
              </Route>
              <Route path="/login" element={<div>Login</div>} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
    // `replace` no añade una nueva entrada: la longitud del historial no crece.
    expect(window.history.length).toBe(before)
  })
})
