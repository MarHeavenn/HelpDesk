import { describe, expect, it } from 'vitest'

import {
  APP_ROUTES,
  canAssignTicket,
  canChangeTicketStatus,
  canCommentTicket,
  canReadSlaPolicies,
  canSetTicketPriority,
  canView,
  firstAllowedRoute,
  navItems,
  routeTitle,
} from '@/lib/permissions'
import type { Rol } from '@/types/domain'

const ADMIN_ROUTES = [
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

const TECHNICIAN_ROUTES = [
  '/',
  '/tickets',
  '/mis-tickets',
  '/tickets/nuevo',
  '/notificaciones',
  '/cuenta/perfil',
] as const

const CLIENT_ROUTES = [
  '/mis-tickets',
  '/tickets/nuevo',
  '/notificaciones',
  '/cuenta/perfil',
] as const

describe('matriz de permisos', () => {
  it('expone todas las rutas de la aplicación', () => {
    expect([...APP_ROUTES]).toEqual([...ADMIN_ROUTES])
  })

  it.each<[Rol, readonly string[]]>([
    ['administrador', ADMIN_ROUTES],
    ['tecnico', TECHNICIAN_ROUTES],
    ['cliente', CLIENT_ROUTES],
  ])('permite al rol %s solo sus rutas', (role, allowed) => {
    for (const route of APP_ROUTES) {
      expect(canView(role, route)).toBe(allowed.includes(route))
    }
  })

  it('niega rutas desconocidas a todos los roles', () => {
    for (const role of ['administrador', 'tecnico', 'cliente'] as const) {
      expect(canView(role, '/ruta-inexistente')).toBe(false)
    }
  })

  it('elige la primera ruta permitida según el rol', () => {
    expect(firstAllowedRoute('administrador')).toBe('/')
    expect(firstAllowedRoute('tecnico')).toBe('/')
    expect(firstAllowedRoute('cliente')).toBe('/mis-tickets')
  })

  it('filtra y ordena los ítems de navegación por rol', () => {
    expect(navItems('administrador').map((item) => item.to)).toEqual(
      ADMIN_ROUTES,
    )
    expect(navItems('tecnico').map((item) => item.to)).toEqual(
      TECHNICIAN_ROUTES,
    )
    expect(navItems('cliente').map((item) => item.to)).toEqual(CLIENT_ROUTES)
  })

  it('usa etiquetas en español y un icono por ítem', () => {
    const adminItems = navItems('administrador')

    expect(adminItems[0]).toMatchObject({
      label: 'Dashboard',
      to: '/',
      icon: 'dashboard',
    })
    expect(adminItems.every((item) => item.label.trim().length > 0)).toBe(true)
    expect(new Set(adminItems.map((item) => item.icon)).size).toBe(
      adminItems.length,
    )
  })

  it('resuelve el título de una ruta conocida y el de una desconocida', () => {
    expect(routeTitle('/tickets')).toBe('Todos los tickets')
    expect(routeTitle('/cuenta/perfil')).toBe('Mi perfil')
    expect(routeTitle('/no-existe')).toBe('Página no encontrada')
  })

  it('limita la prioridad y la política de SLA según el rol', () => {
    expect(canSetTicketPriority('administrador')).toBe(true)
    expect(canSetTicketPriority('tecnico')).toBe(true)
    expect(canSetTicketPriority('cliente')).toBe(false)

    expect(canReadSlaPolicies('administrador')).toBe(true)
    expect(canReadSlaPolicies('tecnico')).toBe(false)
    expect(canReadSlaPolicies('cliente')).toBe(false)
  })

  it('limita el detalle: estado, asignación y comentarios por rol', () => {
    for (const role of ['administrador', 'tecnico'] as Rol[]) {
      expect(canChangeTicketStatus(role)).toBe(true)
      expect(canCommentTicket(role)).toBe(true)
    }
    expect(canChangeTicketStatus('cliente')).toBe(false)
    expect(canCommentTicket('cliente')).toBe(false)

    expect(canAssignTicket('administrador')).toBe(true)
    expect(canAssignTicket('tecnico')).toBe(false)
    expect(canAssignTicket('cliente')).toBe(false)
  })
})
