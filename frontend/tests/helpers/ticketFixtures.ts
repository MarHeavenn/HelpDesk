import { vi } from 'vitest'

import type { TicketsApi } from '@/api/tickets.api'
import type {
  Ticket,
  TicketComment,
  TicketSla,
  TicketSummary,
  Technician,
} from '@/types/ticket'

export const ASSIGNEE = { id: 'u-tech', name: 'Tomás Técnico' }

export function buildSla(overrides: Partial<TicketSla> = {}): TicketSla {
  return {
    target_minutes: 720,
    started_at: '2026-11-10T08:00:00+00:00',
    due_at: '2026-11-20T08:00:00+00:00',
    elapsed_minutes: 60,
    remaining_minutes: 660,
    status: 'en_tiempo',
    near_due: false,
    breached: false,
    ...overrides,
  }
}

export function buildSummary(
  overrides: Partial<TicketSummary> = {},
): TicketSummary {
  return {
    id: 't-00000001',
    title: 'No puedo entrar al portal',
    priority: 'Alta',
    status: 'Abierto',
    assignee: null,
    sla: buildSla(),
    created_at: '2026-11-10T08:00:00+00:00',
    ...overrides,
  }
}

export function buildTicket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    id: 't-00000001',
    title: 'No puedo entrar al portal',
    description: 'Desde ayer no puedo entrar al portal.',
    priority: 'Alta',
    status: 'Abierto',
    assignee: null,
    requester: {
      id: 'u-client',
      name: 'Carla Cliente',
      email: 'carla@example.com',
    },
    sla: buildSla(),
    created_at: '2026-11-10T08:00:00+00:00',
    resolved_at: null,
    requester_id: 'u-client',
    ...overrides,
  }
}

export function buildComment(
  overrides: Partial<TicketComment> = {},
): TicketComment {
  return {
    id: 'c-1',
    ticket_id: 't-00000001',
    body: 'Estamos revisando el caso.',
    author: ASSIGNEE,
    created_at: '2026-11-10T09:00:00+00:00',
    ...overrides,
  }
}

export function createTicketsApiFake(
  overrides: Partial<TicketsApi> = {},
): TicketsApi {
  return {
    createTicket: vi.fn(async () => buildTicket()),
    listMine: vi.fn(async () => []),
    listAssigned: vi.fn(async () => []),
    listAll: vi.fn(async () => []),
    getTicket: vi.fn(async () => buildTicket()),
    setPriority: vi.fn(async () => buildTicket({ priority: 'Media' })),
    setStatus: vi.fn(async () => buildTicket({ status: 'En progreso' })),
    assign: vi.fn(async () => buildTicket({ assignee: ASSIGNEE })),
    listTechnicians: vi.fn(async (): Promise<Technician[]> => [ASSIGNEE]),
    listComments: vi.fn(async (): Promise<TicketComment[]> => []),
    addComment: vi.fn(async () => buildComment()),
    getSlaPolicies: vi.fn(async () => []),
    ...overrides,
  }
}
