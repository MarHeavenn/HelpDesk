import { request } from '@/api/httpClient'
import type { AuthUser } from '@/types/domain'

interface UserResponse {
  id: string
  name: string
  email: string
  role: AuthUser['role']
}

interface MeResponse {
  id: string
  email: string
  role: AuthUser['role']
}

/** Contrato HTTP de autenticación de HU-01. */
export const authApi = {
  login(email: string, password: string): Promise<AuthUser> {
    return request<UserResponse>('/api/auth/login', {
      method: 'POST',
      body: { email, password },
    })
  },

  async me(): Promise<AuthUser> {
    const me = await request<MeResponse>('/api/auth/me')
    return { ...me, name: me.email }
  },

  async logout(): Promise<void> {
    await request<void>('/api/auth/logout', { method: 'POST' })
  },
}
