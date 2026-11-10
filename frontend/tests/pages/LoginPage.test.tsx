import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ApiError } from '@/api/httpClient'
import { AuthProvider, type AuthApi } from '@/context/AuthContext'
import LoginPage from '@/pages/LoginPage'
import type { AuthUser } from '@/types/domain'

const STORAGE_KEY = 'helpdesk.user'

const ADMIN: AuthUser = {
  id: 'u1',
  name: 'Ana Admin',
  email: 'admin@helpdesk.dev',
  role: 'administrador',
}

const CLIENT: AuthUser = {
  id: 'u2',
  name: 'Carla Cliente',
  email: 'carla@example.com',
  role: 'cliente',
}

function createApi(overrides: Partial<AuthApi> = {}): AuthApi {
  return {
    login: vi.fn(async () => ADMIN),
    me: vi.fn(async () => {
      throw new ApiError(401, 'sin sesión')
    }),
    logout: vi.fn(async () => undefined),
    ...overrides,
  }
}

function renderLogin(api: AuthApi) {
  return render(
    <AuthProvider api={api}>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>inicio</p>} />
          <Route path="/mis-tickets" element={<p>mis tickets</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

async function fillCredentials(email: string, password: string) {
  const user = userEvent.setup()
  const emailInput = await screen.findByLabelText(/correo electrónico/i)
  const passwordInput = screen.getByLabelText(/contraseña/i)

  if (email) await user.type(emailInput, email)
  if (password) await user.type(passwordInput, password)

  return user
}

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('LoginPage', () => {
  it('valida correo y contraseña antes de llamar a la API', async () => {
    const api = createApi()
    renderLogin(api)

    const user = await fillCredentials('', '')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(screen.getByText('Ingresa tu correo')).toBeInTheDocument()
    expect(screen.getByText('Ingresa tu contraseña')).toBeInTheDocument()
    expect(api.login).not.toHaveBeenCalled()
  })

  it('rechaza un correo con formato inválido', async () => {
    const api = createApi()
    renderLogin(api)

    const user = await fillCredentials('ana', 'secreto123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(screen.getByText('Ingresa un correo válido')).toBeInTheDocument()
    expect(api.login).not.toHaveBeenCalled()
  })

  it('muestra el mensaje de credenciales incorrectas ante un 401', async () => {
    const api = createApi({
      login: vi.fn(async () => {
        throw new ApiError(401, 'invalid credentials')
      }),
    })
    renderLogin(api)

    const user = await fillCredentials('ana@example.com', 'incorrecta')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Correo o contraseña incorrectos',
    )
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled()
  })

  it('muestra el detalle del backend ante un error de validación 422', async () => {
    const api = createApi({
      login: vi.fn(async () => {
        throw new ApiError(422, 'La contraseña es demasiado corta')
      }),
    })
    renderLogin(api)

    const user = await fillCredentials('ana@example.com', 'x')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La contraseña es demasiado corta',
    )
  })

  it('inicia sesión, guarda la identidad y redirige a la ruta del rol', async () => {
    const api = createApi()
    renderLogin(api)

    const user = await fillCredentials('  admin@helpdesk.dev  ', 'secreto123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText('inicio')).toBeInTheDocument()
    expect(api.login).toHaveBeenCalledWith('admin@helpdesk.dev', 'secreto123')

    const stored = localStorage.getItem(STORAGE_KEY) ?? ''
    expect(JSON.parse(stored)).toMatchObject({
      id: 'u1',
      role: 'administrador',
    })
    expect(stored).not.toContain('secreto123')
  })

  it('deshabilita el botón mientras espera la respuesta', async () => {
    let resolveLogin: (user: AuthUser) => void = () => undefined
    const api = createApi({
      login: vi.fn(
        () =>
          new Promise<AuthUser>((resolve) => {
            resolveLogin = resolve
          }),
      ),
    })
    renderLogin(api)

    const user = await fillCredentials('admin@helpdesk.dev', 'secreto123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    const pending = screen.getByRole('button', { name: 'Entrando...' })
    expect(pending).toBeDisabled()

    resolveLogin(ADMIN)
    expect(await screen.findByText('inicio')).toBeInTheDocument()
  })

  it('redirige a su ruta permitida si ya hay sesión y abre /login', async () => {
    const api = createApi({ me: vi.fn(async () => CLIENT) })
    localStorage.setItem(STORAGE_KEY, JSON.stringify(CLIENT))

    renderLogin(api)

    expect(await screen.findByText('mis tickets')).toBeInTheDocument()
    expect(screen.queryByLabelText(/correo electrónico/i)).not.toBeInTheDocument()
    expect(api.login).not.toHaveBeenCalled()
  })

  it('vuelve a habilitar el formulario si falla la red', async () => {
    const api = createApi({
      login: vi.fn(async () => {
        throw new Error('network down')
      }),
    })
    renderLogin(api)

    const user = await fillCredentials('ana@example.com', 'secreto123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled(),
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      'No se pudo iniciar sesión',
    )
  })
})
