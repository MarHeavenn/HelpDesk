export const ROLES = ['administrador', 'supervisor', 'tecnico', 'cliente'] as const

export type Rol = (typeof ROLES)[number]

export interface AuthUser {
  id: string
  name: string
  email: string
  role: Rol
}
