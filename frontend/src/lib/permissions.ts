import { strings } from '@/lib/strings'
import type { Rol } from '@/types/domain'

export const APP_ROUTES = [
  '/',
  '/tickets',
  '/mis-tickets',
  '/tickets/nuevo',
  '/tecnicos',
  '/sla',
  '/usuarios',
  '/empresas',
  '/notificaciones',
  '/cuenta/perfil',
] as const

export type AppRoute = (typeof APP_ROUTES)[number]

const TECHNICIAN_ROUTES: readonly AppRoute[] = [
  '/',
  '/tickets',
  '/mis-tickets',
  '/tickets/nuevo',
  '/notificaciones',
  '/cuenta/perfil',
]

const CLIENT_ROUTES: readonly AppRoute[] = [
  '/mis-tickets',
  '/tickets/nuevo',
  '/notificaciones',
  '/cuenta/perfil',
]

const PERMISSIONS: Record<Rol, readonly AppRoute[]> = {
  administrador: APP_ROUTES,
  tecnico: TECHNICIAN_ROUTES,
  cliente: CLIENT_ROUTES,
}

/** Indica si el rol puede ver la ruta indicada. */
export function canView(role: Rol, path: string): boolean {
  return PERMISSIONS[role].some((route) => route === path)
}

/** Primera ruta permitida para el rol, usada en guards y redirecciones. */
export function firstAllowedRoute(role: Rol): AppRoute {
  return role === 'cliente' ? '/mis-tickets' : '/'
}

/**
 * Solo administrador y técnico pueden fijar la prioridad de un ticket ajeno
 * (HU-03); el cliente la elige como intención, pero el backend no se la acepta.
 */
export function canSetTicketPriority(role: Rol): boolean {
  return role === 'administrador' || role === 'tecnico'
}

/** La política de SLA vigente solo es legible por el administrador (HU-14). */
export function canReadSlaPolicies(role: Rol): boolean {
  return role === 'administrador'
}

export type NavIcon =
  | 'dashboard'
  | 'tickets'
  | 'my-tickets'
  | 'create-ticket'
  | 'technicians'
  | 'sla'
  | 'users'
  | 'companies'
  | 'notifications'
  | 'account'

export interface NavItem {
  label: string
  to: AppRoute
  icon: NavIcon
}

const NAV_ITEMS: readonly NavItem[] = [
  { label: strings.nav.dashboard, to: '/', icon: 'dashboard' },
  { label: strings.nav.tickets, to: '/tickets', icon: 'tickets' },
  { label: strings.nav.myTickets, to: '/mis-tickets', icon: 'my-tickets' },
  {
    label: strings.nav.createTicket,
    to: '/tickets/nuevo',
    icon: 'create-ticket',
  },
  { label: strings.nav.technicians, to: '/tecnicos', icon: 'technicians' },
  { label: strings.nav.sla, to: '/sla', icon: 'sla' },
  { label: strings.nav.users, to: '/usuarios', icon: 'users' },
  { label: strings.nav.companies, to: '/empresas', icon: 'companies' },
  {
    label: strings.nav.notifications,
    to: '/notificaciones',
    icon: 'notifications',
  },
  { label: strings.nav.account, to: '/cuenta/perfil', icon: 'account' },
]

/** Ítems de navegación visibles para el rol. */
export function navItems(role: Rol): NavItem[] {
  return NAV_ITEMS.filter((item) => canView(role, item.to))
}

/** Título legible de una ruta; las desconocidas usan el título de 404. */
export function routeTitle(path: string): string {
  const titles: Record<string, string> = strings.routes.titles
  return titles[path] ?? strings.routes.notFoundTitle
}
