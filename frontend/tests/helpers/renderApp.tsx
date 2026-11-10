import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

import { AuthProvider, type AuthApi } from '@/context/AuthContext'
import type { AuthUser } from '@/types/domain'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  })
}

export const ADMIN: AuthUser = {
  id: 'u-admin',
  name: 'Ana Admin',
  email: 'admin@helpdesk.dev',
  role: 'administrador',
}

export const TECNICO: AuthUser = {
  id: 'u-tech',
  name: 'Tomás Técnico',
  email: 'tecnico@helpdesk.dev',
  role: 'tecnico',
}

export const CLIENTE: AuthUser = {
  id: 'u-client',
  name: 'Carla Cliente',
  email: 'carla@example.com',
  role: 'cliente',
}

export function createAuthApi(
  user: AuthUser = ADMIN,
  overrides: Partial<AuthApi> = {},
): AuthApi {
  return {
    login: vi.fn(async () => user),
    me: vi.fn(async () => user),
    logout: vi.fn(async () => undefined),
    ...overrides,
  }
}

export function renderApp(
  ui: ReactNode,
  options: {
    user?: AuthUser
    route?: string
    api?: AuthApi
    queryClient?: QueryClient
  } = {},
) {
  const user = options.user ?? ADMIN
  const api = options.api ?? createAuthApi(user)
  const queryClient = options.queryClient ?? createQueryClient()

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider api={api}>
        <MemoryRouter initialEntries={[options.route ?? '/']}>
          <Routes>
            <Route path="/login" element={<p>pantalla de login</p>} />
            <Route path="*" element={ui} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}
