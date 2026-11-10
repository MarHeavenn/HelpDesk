import { vi } from 'vitest'

import type { DashboardApi } from '@/api/dashboard.api'
import type { TicketDashboard } from '@/types/dashboard'

export function buildTicketDashboard(
  overrides: Partial<TicketDashboard> = {},
): TicketDashboard {
  return {
    total_tickets: 6,
    by_status: [
      { status: 'Abierto', count: 2 },
      { status: 'En progreso', count: 2 },
      { status: 'Resuelto', count: 1 },
      { status: 'Cerrado', count: 1 },
    ],
    by_priority: [
      { priority: 'Crítica', label: 'Crítica', count: 1 },
      { priority: 'Alta', label: 'Alta', count: 2 },
      { priority: 'Media', label: 'Media', count: 1 },
      { priority: 'Baja', label: 'Baja', count: 1 },
      { priority: null, label: 'Sin prioridad', count: 1 },
    ],
    by_assignee: [
      { technician: null, label: 'Sin asignar', count: 2 },
      {
        technician: { id: 'tech-1', name: 'Ana' },
        label: 'Ana',
        count: 2,
      },
      {
        technician: { id: 'tech-2', name: 'Luis' },
        label: 'Luis',
        count: 2,
      },
    ],
    recent_tickets: [
      {
        id: 'ticket-1',
        title: 'No puedo iniciar sesión',
        priority: 'Crítica',
        status: 'Abierto',
        assignee: { id: 'tech-1', name: 'Ana' },
        created_at: '2026-11-02T11:59:00+00:00',
      },
      {
        id: 'ticket-2',
        title: 'Error al adjuntar archivo',
        priority: 'Alta',
        status: 'En progreso',
        assignee: { id: 'tech-1', name: 'Ana' },
        created_at: '2026-11-02T11:58:00+00:00',
      },
      {
        id: 'ticket-3',
        title: 'Solicitud de acceso',
        priority: 'Media',
        status: 'Resuelto',
        assignee: { id: 'tech-2', name: 'Luis' },
        created_at: '2026-11-02T11:57:00+00:00',
      },
      {
        id: 'ticket-4',
        title: 'Factura duplicada',
        priority: 'Baja',
        status: 'Cerrado',
        assignee: null,
        created_at: '2026-11-02T11:56:00+00:00',
      },
      {
        id: 'ticket-5',
        title: 'Consulta de horarios',
        priority: null,
        status: 'Abierto',
        assignee: null,
        created_at: '2026-11-02T11:55:00+00:00',
      },
    ],
    generated_at: '2026-11-02T12:00:00+00:00',
    ...overrides,
  }
}

export function createDashboardApi(
  overrides: Partial<DashboardApi> = {},
): DashboardApi {
  return {
    getTickets: vi.fn(async () => buildTicketDashboard()),
    ...overrides,
  }
}
