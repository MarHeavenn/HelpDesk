import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ApiError, setUnauthorizedHandler } from '@/api/httpClient'
import {
  AuthProvider,
  useAuth,
  type AuthApi,
} from '@/context/AuthContext'
import type { AuthUser } from '@/types/domain'

const STORAGE_KEY = 'helpdesk.user'

const ANA: AuthUser = {
  id: 'u1',
  name: 'Ana Torres',
  email: 'ana@example.com',
  role: 'tecnico',
}

function createApi(overrides: Partial<AuthApi> = {}): AuthApi {
  return {
    login: vi.fn(async (email: string) => ({
      ...ANA,
      email,
    })),
    me: vi.fn(async () => ({ ...ANA, name: ANA.email })),
    logout: vi.fn(async () => undefined),
    ...overrides,
  }
}

function Probe() {
  const { user, status, error, login, logout } = useAuth()

  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{user?.name ?? ''}</span>
      <span data-testid="role">{user?.role ?? ''}</span>
      <span data-testid="error">{error ?? ''}</span>
      <button type="button" onClick={() => void login(ANA.email, 'secreto')}>
        login
      </button>
      <button type="button" onClick={() => void logout()}>
        logout
      </button>
    </div>
  )
}

function renderAuth(api: AuthApi) {
  return render(
    <AuthProvider api={api}>
      <Probe />
    </AuthProvider>,
  )
}

function storeUser(user: AuthUser) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
}

afterEach(() => {
  localStorage.clear()
  setUnauthorizedHandler(null)
  vi.restoreAllMocks()
})

describe('AuthContext', () => {
  it('valida la sesión al montar y conserva el nombre guardado', async () => {
    storeUser(ANA)
    const api = createApi()

    renderAuth(api)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )
    expect(api.me).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('user')).toHaveTextContent('Ana Torres')
    expect(screen.getByTestId('role')).toHaveTextContent('tecnico')
  })

  it('pasa a anónimo y limpia el almacenamiento si la sesión responde 401', async () => {
    storeUser(ANA)
    const api = createApi({
      me: vi.fn(async () => {
        throw new ApiError(401, 'sesión inválida')
      }),
    })

    renderAuth(api)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('anonymous'),
    )
    expect(screen.getByTestId('user')).toBeEmptyDOMElement()
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('mantiene la sesión local y muestra error si falla la red', async () => {
    storeUser(ANA)
    const api = createApi({
      me: vi.fn(async () => {
        throw new Error('network down')
      }),
    })

    renderAuth(api)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
    expect(screen.getByTestId('user')).toHaveTextContent('Ana Torres')
    expect(screen.getByTestId('error')).not.toBeEmptyDOMElement()
  })

  it('inicia sesión, guarda el usuario y pasa a autenticado', async () => {
    const api = createApi({
      me: vi.fn(async () => {
        throw new ApiError(401, 'sin sesión')
      }),
    })
    const user = userEvent.setup()

    renderAuth(api)
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('anonymous'),
    )

    await user.click(screen.getByRole('button', { name: 'login' }))

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )
    expect(api.login).toHaveBeenCalledWith(ANA.email, 'secreto')
    expect(screen.getByTestId('user')).toHaveTextContent('Ana Torres')
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')).toMatchObject(
      { id: 'u1', role: 'tecnico' },
    )
  })

  it('cierra sesión, limpia el usuario y llama a la API', async () => {
    storeUser(ANA)
    const api = createApi()
    const user = userEvent.setup()

    renderAuth(api)
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )

    await user.click(screen.getByRole('button', { name: 'logout' }))

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('anonymous'),
    )
    expect(api.logout).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
