import { PRIORITIES, STATUSES, type TicketSummary } from '@/types/ticket'

export const PAGE_SIZE = 10

export const TICKET_SORTS = ['recent', 'oldest', 'priority', 'sla'] as const
export type TicketSort = (typeof TICKET_SORTS)[number]

export type TicketListScope = 'all' | 'mine' | 'assigned'

export interface TicketFilters {
  query: string
  /** `'all'` o una prioridad del catálogo. */
  priority: string
  /** `'all'` o un estado del catálogo. */
  status: string
  /** `'all'`, `'unassigned'` o el identificador de un técnico. */
  assignee: string
  sort: TicketSort
  page: number
}

export const DEFAULT_TICKET_FILTERS: TicketFilters = {
  query: '',
  priority: 'all',
  status: 'all',
  assignee: 'all',
  sort: 'recent',
  page: 1,
}

const PRIORITY_ORDER: Record<string, number> = {
  Crítica: 0,
  Alta: 1,
  Media: 2,
  Baja: 3,
}

function timestamp(value: string | null | undefined): number {
  if (!value) return Number.POSITIVE_INFINITY
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? Number.POSITIVE_INFINITY : time
}

/** Busca por identificador (con o sin `#`) o por título, sin distinguir mayúsculas. */
function matchesQuery(ticket: TicketSummary, query: string): boolean {
  const normalized = query.trim().toLocaleLowerCase('es-CO')
  if (!normalized) return true
  const term = normalized.startsWith('#') ? normalized.slice(1) : normalized
  return (
    ticket.title.toLocaleLowerCase('es-CO').includes(normalized) ||
    ticket.id.toLocaleLowerCase('es-CO').includes(term)
  )
}

/** Aplica los filtros combinables del listado. No muta la entrada. */
export function filterTickets(
  tickets: readonly TicketSummary[],
  filters: TicketFilters,
): TicketSummary[] {
  return tickets.filter((ticket) => {
    if (!matchesQuery(ticket, filters.query)) return false
    if (filters.priority !== 'all' && ticket.priority !== filters.priority) {
      return false
    }
    if (filters.status !== 'all' && ticket.status !== filters.status) {
      return false
    }
    if (filters.assignee === 'unassigned' && ticket.assignee) return false
    if (
      filters.assignee !== 'all' &&
      filters.assignee !== 'unassigned' &&
      ticket.assignee?.id !== filters.assignee
    ) {
      return false
    }
    return true
  })
}

/**
 * Ordena sin mutar la entrada. Prioridad más alta y SLA más próximo van
 * primero; los tickets sin prioridad (sin SLA) quedan al final. Los empates
 * se resuelven por fecha de creación descendente.
 */
export function sortTickets(
  tickets: readonly TicketSummary[],
  sort: TicketSort,
): TicketSummary[] {
  const copy = [...tickets]
  copy.sort((a, b) => {
    if (sort === 'oldest') return timestamp(a.created_at) - timestamp(b.created_at)
    if (sort === 'priority') {
      const aRank = a.priority ? (PRIORITY_ORDER[a.priority] ?? 99) : 100
      const bRank = b.priority ? (PRIORITY_ORDER[b.priority] ?? 99) : 100
      if (aRank !== bRank) return aRank - bRank
    }
    if (sort === 'sla') {
      const aDue = timestamp(a.sla?.due_at)
      const bDue = timestamp(b.sla?.due_at)
      if (aDue !== bDue) return aDue - bDue
    }
    return timestamp(b.created_at) - timestamp(a.created_at)
  })
  return copy
}

export interface TicketPage<T> {
  items: T[]
  total: number
  pages: number
  page: number
  from: number
  to: number
}

function normalizePage(page: number, pages: number): number {
  if (!Number.isInteger(page) || page < 1) return 1
  if (pages > 0 && page > pages) return 1
  return page
}

/** Pagina de 10 en 10; una página fuera de rango vuelve a la primera. */
export function paginateTickets(
  tickets: readonly TicketSummary[],
  page: number,
  pageSize: number = PAGE_SIZE,
): TicketPage<TicketSummary> {
  const total = tickets.length
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const current = normalizePage(page, pages)
  const start = (current - 1) * pageSize
  const items = tickets.slice(start, start + pageSize)
  return {
    items,
    total,
    pages,
    page: current,
    from: total === 0 ? 0 : start + 1,
    to: start + items.length,
  }
}

/** Lee y normaliza los filtros de la query string (valores inválidos → «todos»). */
export function parseTicketQuery(params: URLSearchParams): TicketFilters {
  const priority = params.get('priority')
  const status = params.get('status')
  const assignee = params.get('assignee')
  const sort = params.get('sort')
  const rawPage = Number(params.get('page'))

  return {
    query: params.get('q')?.trim() ?? '',
    priority:
      priority && (PRIORITIES as readonly string[]).includes(priority)
        ? priority
        : 'all',
    status:
      status && (STATUSES as readonly string[]).includes(status)
        ? status
        : 'all',
    assignee: assignee && assignee.trim() ? assignee.trim() : 'all',
    sort: sort && (TICKET_SORTS as readonly string[]).includes(sort)
      ? (sort as TicketSort)
      : 'recent',
    page: Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1,
  }
}

/** Serializa los filtros a la query string, omitiendo los valores por defecto. */
export function ticketQueryToParams(filters: TicketFilters): URLSearchParams {
  const params = new URLSearchParams()
  const query = filters.query.trim()
  if (query) params.set('q', query)
  if (filters.priority !== 'all') params.set('priority', filters.priority)
  if (filters.status !== 'all') params.set('status', filters.status)
  if (filters.assignee !== 'all') params.set('assignee', filters.assignee)
  if (filters.sort !== 'recent') params.set('sort', filters.sort)
  if (filters.page > 1) params.set('page', String(filters.page))
  return params
}

/** Indica si hay algún filtro distinto del valor por defecto (sin contar la página). */
export function hasActiveTicketFilters(filters: TicketFilters): boolean {
  return (
    filters.query.trim().length > 0 ||
    filters.priority !== 'all' ||
    filters.status !== 'all' ||
    filters.assignee !== 'all'
  )
}

/** Técnicos presentes en el listado, ordenados por nombre, para el filtro. */
export function technicianOptions(
  tickets: readonly TicketSummary[],
): { id: string; name: string }[] {
  const byId = new Map<string, string>()
  for (const ticket of tickets) {
    if (ticket.assignee) byId.set(ticket.assignee.id, ticket.assignee.name)
  }
  return [...byId.entries()]
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name, 'es-CO'))
}

/** Tiempo objetivo de SLA en minutos, legible en horas cuando es exacto. */
export function formatTargetMinutes(minutes: number): string {
  if (minutes >= 60 && minutes % 60 === 0) {
    const hours = minutes / 60
    return hours === 1 ? '1 hora' : `${hours} horas`
  }
  return minutes === 1 ? '1 minuto' : `${minutes} minutos`
}
