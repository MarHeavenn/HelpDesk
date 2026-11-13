import { describe, expect, it } from 'vitest'

import {
  DEFAULT_TICKET_FILTERS,
  filterTickets,
  formatTargetMinutes,
  hasActiveTicketFilters,
  paginateTickets,
  parseTicketQuery,
  sortTickets,
  technicianOptions,
  ticketQueryToParams,
} from '@/lib/tickets'
import { buildSla, buildSummary } from '../helpers/ticketFixtures'

const openHigh = buildSummary({
  id: 'aaa11111',
  title: 'No puedo entrar al portal',
  priority: 'Alta',
  status: 'Abierto',
  created_at: '2026-11-10T08:00:00+00:00',
  sla: buildSla({ due_at: '2026-11-20T08:00:00+00:00' }),
})
const closedLow = buildSummary({
  id: 'bbb22222',
  title: 'Solicitud de licencia',
  priority: 'Baja',
  status: 'Cerrado',
  created_at: '2026-11-12T08:00:00+00:00',
  sla: buildSla({ status: 'cumplido', due_at: '2026-11-30T08:00:00+00:00' }),
})
const unassignedCritical = buildSummary({
  id: 'ccc33333',
  title: 'Servidor caído',
  priority: 'Crítica',
  status: 'En progreso',
  created_at: '2026-11-11T08:00:00+00:00',
  sla: buildSla({ status: 'en_riesgo', due_at: '2026-11-13T08:00:00+00:00' }),
})
const noPriority = buildSummary({
  id: 'ddd44444',
  title: 'Consulta general',
  priority: null,
  status: 'Abierto',
  created_at: '2026-11-09T08:00:00+00:00',
  sla: null,
})
const assignedHigh = buildSummary({
  id: 'eee55555',
  title: 'Error de facturación',
  priority: 'Alta',
  status: 'Resuelto',
  assignee: { id: 'u-tech', name: 'Tomás Técnico' },
  created_at: '2026-11-08T08:00:00+00:00',
})

const ALL = [openHigh, closedLow, unassignedCritical, noPriority, assignedHigh]

describe('filterTickets', () => {
  it('busca por título e identificador sin distinguir mayúsculas', () => {
    expect(
      filterTickets(ALL, { ...DEFAULT_TICKET_FILTERS, query: 'PORTAL' }),
    ).toEqual([openHigh])
    expect(
      filterTickets(ALL, { ...DEFAULT_TICKET_FILTERS, query: '#ccc3' }),
    ).toEqual([unassignedCritical])
  })

  it('combina prioridad, estado y técnico', () => {
    expect(
      filterTickets(ALL, {
        ...DEFAULT_TICKET_FILTERS,
        priority: 'Alta',
        status: 'Resuelto',
        assignee: 'u-tech',
      }),
    ).toEqual([assignedHigh])
    expect(
      filterTickets(ALL, { ...DEFAULT_TICKET_FILTERS, assignee: 'unassigned' }),
    ).toEqual([openHigh, closedLow, unassignedCritical, noPriority])
  })

  it('devuelve todo con los filtros por defecto', () => {
    expect(filterTickets(ALL, DEFAULT_TICKET_FILTERS)).toEqual(ALL)
  })
})

describe('sortTickets', () => {
  it('ordena por más recientes y más antiguos sin mutar la entrada', () => {
    const original = [...ALL]
    expect(sortTickets(ALL, 'recent').map((ticket) => ticket.id)).toEqual([
      'bbb22222',
      'ccc33333',
      'aaa11111',
      'ddd44444',
      'eee55555',
    ])
    expect(sortTickets(ALL, 'oldest')[0].id).toBe('eee55555')
    expect(ALL).toEqual(original)
  })

  it('ordena por prioridad dejando las sin prioridad al final', () => {
    expect(sortTickets(ALL, 'priority').map((ticket) => ticket.priority)).toEqual(
      ['Crítica', 'Alta', 'Alta', 'Baja', null],
    )
  })

  it('ordena por SLA más próximo y deja al final los que no tienen SLA', () => {
    const sorted = sortTickets(ALL, 'sla')
    expect(sorted[sorted.length - 1].id).toBe('ddd44444')
    expect(sorted[0].id).toBe('ccc33333')
  })
})

describe('paginateTickets', () => {
  const many = Array.from({ length: 12 }, (_, index) =>
    buildSummary({ id: `t-${index}`, title: `Ticket ${index}` }),
  )

  it('pagina de 10 en 10 con el rango visible', () => {
    const first = paginateTickets(many, 1)
    expect(first.items).toHaveLength(10)
    expect(first).toMatchObject({ total: 12, pages: 2, page: 1, from: 1, to: 10 })

    const second = paginateTickets(many, 2)
    expect(second.items).toHaveLength(2)
    expect(second).toMatchObject({ page: 2, from: 11, to: 12 })
  })

  it('normaliza una página fuera de rango a la primera', () => {
    expect(paginateTickets(many, 99)).toMatchObject({ page: 1, from: 1 })
    expect(paginateTickets(many, 0)).toMatchObject({ page: 1 })
  })

  it('devuelve una página vacía coherente sin tickets', () => {
    expect(paginateTickets([], 1)).toMatchObject({
      items: [],
      total: 0,
      pages: 1,
      from: 0,
      to: 0,
    })
  })
})

describe('query string', () => {
  it('normaliza valores inválidos a los predeterminados', () => {
    const filters = parseTicketQuery(
      new URLSearchParams(
        'priority=Urgente&status=Perdido&sort=caro&page=-3&q=  portal  ',
      ),
    )

    expect(filters).toEqual({
      query: 'portal',
      priority: 'all',
      status: 'all',
      assignee: 'all',
      sort: 'recent',
      page: 1,
    })
  })

  it('lee filtros válidos y conserva el técnico', () => {
    expect(
      parseTicketQuery(
        new URLSearchParams(
          'priority=Alta&status=Abierto&assignee=u-tech&sort=sla&page=2',
        ),
      ),
    ).toMatchObject({
      priority: 'Alta',
      status: 'Abierto',
      assignee: 'u-tech',
      sort: 'sla',
      page: 2,
    })
  })

  it('serializa omitiendo los valores por defecto', () => {
    expect(ticketQueryToParams(DEFAULT_TICKET_FILTERS).toString()).toBe('')
    expect(
      ticketQueryToParams({
        ...DEFAULT_TICKET_FILTERS,
        query: ' servidor ',
        priority: 'Alta',
        status: 'En progreso',
        assignee: 'u-tech',
        sort: 'priority',
        page: 3,
      }).toString(),
    ).toBe(
      'q=servidor&priority=Alta&status=En+progreso&assignee=u-tech&sort=priority&page=3',
    )
  })

  it('detecta filtros activos sin contar la página ni el orden', () => {
    expect(hasActiveTicketFilters({ ...DEFAULT_TICKET_FILTERS, page: 2 })).toBe(
      false,
    )
    expect(
      hasActiveTicketFilters({ ...DEFAULT_TICKET_FILTERS, status: 'Abierto' }),
    ).toBe(true)
  })
})

describe('technicianOptions y formato', () => {
  it('deduplica técnicos y los ordena por nombre', () => {
    const tickets = [
      assignedHigh,
      buildSummary({ id: 'x', assignee: { id: 'u-ana', name: 'Ana' } }),
      buildSummary({ id: 'y', assignee: { id: 'u-tech', name: 'Tomás Técnico' } }),
    ]
    expect(technicianOptions(tickets)).toEqual([
      { id: 'u-ana', name: 'Ana' },
      { id: 'u-tech', name: 'Tomás Técnico' },
    ])
  })

  it('formatea el objetivo de SLA en minutos u horas', () => {
    expect(formatTargetMinutes(720)).toBe('12 horas')
    expect(formatTargetMinutes(60)).toBe('1 hora')
    expect(formatTargetMinutes(90)).toBe('90 minutos')
    expect(formatTargetMinutes(1)).toBe('1 minuto')
  })
})
