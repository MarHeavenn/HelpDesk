import { vi } from 'vitest'

import type { DashboardApi } from '@/api/dashboard.api'
import type {
  SlaDashboard,
  SlaPriorityBreakdown,
  TicketDashboard,
} from '@/types/dashboard'

const PRIORITY_BREAKDOWN: SlaPriorityBreakdown[] = [
  {
    priority: 'Crítica',
    en_tiempo: 1,
    en_riesgo: 0,
    cumplido: 1,
    incumplido: 0,
    compliance_percentage: 100,
  },
  {
    priority: 'Alta',
    en_tiempo: 0,
    en_riesgo: 1,
    cumplido: 0,
    incumplido: 1,
    compliance_percentage: 0,
  },
  {
    priority: 'Media',
    en_tiempo: 0,
    en_riesgo: 0,
    cumplido: 1,
    incumplido: 0,
    compliance_percentage: 100,
  },
  {
    priority: 'Baja',
    en_tiempo: 0,
    en_riesgo: 0,
    cumplido: 1,
    incumplido: 0,
    compliance_percentage: 100,
  },
]

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

export function buildSlaDashboard(
  overrides: Partial<SlaDashboard> = {},
): SlaDashboard {
  return {
    total_evaluated: 6,
    en_tiempo: 1,
    en_riesgo: 1,
    cumplido: 3,
    incumplido: 1,
    sin_sla: 1,
    compliance_percentage: 66.67,
    closed_without_resolved_at: 1,
    threshold_percent: 20,
    period_days: 30,
    by_priority: PRIORITY_BREAKDOWN,
    generated_at: '2026-11-02T12:00:00+00:00',
    ...overrides,
  }
}

export function buildEmptySlaDashboard(): SlaDashboard {
  return buildSlaDashboard({
    total_evaluated: 0,
    en_tiempo: 0,
    en_riesgo: 0,
    cumplido: 0,
    incumplido: 0,
    sin_sla: 2,
    compliance_percentage: 0,
    closed_without_resolved_at: 0,
    by_priority: PRIORITY_BREAKDOWN.map((item) => ({
      ...item,
      en_tiempo: 0,
      en_riesgo: 0,
      cumplido: 0,
      incumplido: 0,
      compliance_percentage: 0,
    })),
  })
}

export function createDashboardApi(
  overrides: Partial<DashboardApi> = {},
): DashboardApi {
  return {
    getTickets: vi.fn(async () => buildTicketDashboard()),
    getSla: vi.fn(async (days) =>
      buildSlaDashboard({ period_days: days }),
    ),
    ...overrides,
  }
}
