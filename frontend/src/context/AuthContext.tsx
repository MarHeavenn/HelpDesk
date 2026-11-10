import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { authApi } from '@/api/auth.api'
import { ApiError, setUnauthorizedHandler } from '@/api/httpClient'
import { ROLES, type AuthUser, type Rol } from '@/types/domain'

const STORAGE_KEY = 'helpdesk.user'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'error'

export interface AuthApi {
  login(email: string, password: string): Promise<AuthUser>
  me(): Promise<AuthUser>
  logout(): Promise<void>
}

export interface AuthContextValue {
  user: AuthUser | null
  status: AuthStatus
  isLoading: boolean
  error: string | null
  login(email: string, password: string): Promise<AuthUser>
  logout(): Promise<void>
  refresh(): Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function isRol(value: unknown): value is Rol {
  return typeof value === 'string' && ROLES.some((role) => role === value)
}

function readStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null

    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null

    const candidate = parsed as Partial<AuthUser>
    if (
      typeof candidate.id !== 'string' ||
      typeof candidate.name !== 'string' ||
      typeof candidate.email !== 'string' ||
      !isRol(candidate.role)
    ) {
      return null
    }

    return {
      id: candidate.id,
      name: candidate.name,
      email: candidate.email,
      role: candidate.role,
    }
  } catch {
    return null
  }
}

function writeStoredUser(user: AuthUser | null): void {
  try {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Almacenamiento no disponible (modo privado o cuota): la sesión sigue en memoria.
  }
}

function withStoredName(me: AuthUser, stored: AuthUser | null): AuthUser {
  if (stored && stored.id === me.id && stored.name.trim()) {
    return { ...me, name: stored.name }
  }
  return me
}

export function AuthProvider({
  children,
  api = authApi,
}: {
  children: ReactNode
  api?: AuthApi
}) {
  const [user, setUser] = useState<AuthUser | null>(() => readStoredUser())
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const apiRef = useRef(api)
  apiRef.current = api

  const clearSession = useCallback(() => {
    setUser(null)
    setStatus('anonymous')
    setError(null)
    writeStoredUser(null)
  }, [])

  const refresh = useCallback(async () => {
    setStatus('loading')
    setError(null)

    try {
      const me = await apiRef.current.me()
      const authenticated = withStoredName(me, readStoredUser())
      setUser(authenticated)
      writeStoredUser(authenticated)
      setStatus('authenticated')
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        clearSession()
        return
      }
      setStatus('error')
      setError('No se pudo validar la sesión. Inténtalo de nuevo.')
    }
  }, [clearSession])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    setUnauthorizedHandler(clearSession)
    return () => setUnauthorizedHandler(null)
  }, [clearSession])

  const login = useCallback(async (email: string, password: string) => {
    setError(null)
    const authenticated = await apiRef.current.login(email, password)
    setUser(authenticated)
    writeStoredUser(authenticated)
    setStatus('authenticated')
    return authenticated
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiRef.current.logout()
    } finally {
      clearSession()
    }
  }, [clearSession])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      isLoading: status === 'loading',
      error,
      login,
      logout,
      refresh,
    }),
    [user, status, error, login, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// El hook convive con el provider para mantener una única fuente de sesión.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth debe usarse dentro de AuthProvider')
  }
  return context
}
