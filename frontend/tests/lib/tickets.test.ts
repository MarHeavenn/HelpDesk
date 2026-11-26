import { describe, expect, it } from 'vitest'

import {
  DEFAULT_TICKET_FILTERS,
  clearTicketFilters,
  filterTickets,
  formatTargetMinutes,
  hasActiveTicketFilters,
  paginateTickets,
  parseTicketQuery,
  sortTickets,
  technicianOptions,
  ticketQueryToParams,
  type TicketFilters,
} from '@/lib/tickets'
import { PRIORITIES, STATUSES } from '@/types/ticket'
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

describe('filterTickets HU-17: criterios puros', () => {
  it('inicia solicitante vacío y SLA en Todos', () => {
    expect(DEFAULT_TICKET_FILTERS).toMatchObject({ requester: '', sla: 'all' })
  })

  it.each([
    ['', ALL],
    ['   ', ALL],
    ['#', ALL],
    ['  #  ', ALL],
    ['  PORTAL  ', [openHigh]],
    [' AAA1 ', [openHigh]],
    [' #AaA1 ', [openHigh]],
    [' LICEN ', [closedLow]],
    ['sin coincidencia', []],
  ])('normaliza la búsqueda %j por ID o título', (query, expected) => {
    expect(filterTickets(ALL, { ...DEFAULT_TICKET_FILTERS, query })).toEqual(expected)
  })

  it.each(STATUSES)('compara exactamente el estado %s', (status) => {
    const tickets = STATUSES.map((value) => buildSummary({ id: value, status: value }))
    expect(filterTickets(tickets, { ...DEFAULT_TICKET_FILTERS, status })).toEqual([
      tickets[STATUSES.indexOf(status)],
    ])
  })

  it.each(PRIORITIES)('compara exactamente la prioridad %s y excluye null', (priority) => {
    const tickets = [...PRIORITIES.map((value) => buildSummary({ id: value, priority: value })), noPriority]
    expect(filterTickets(tickets, { ...DEFAULT_TICKET_FILTERS, priority })).toEqual([
      tickets[PRIORITIES.indexOf(priority)],
    ])
    expect(filterTickets(tickets, DEFAULT_TICKET_FILTERS)).toEqual(tickets)
  })

  it.each([
    ['all', ALL],
    ['u-tech', [assignedHigh]],
    ['unassigned', [openHigh, closedLow, unassignedCritical, noPriority]],
    ['otro-tecnico', []],
  ])('conserva el criterio de técnico %s', (assignee, expected) => {
    expect(filterTickets(ALL, { ...DEFAULT_TICKET_FILTERS, assignee })).toEqual(expected)
  })

  const named = buildSummary({ id: 'named', requester: { name: 'María Pérez' } })
  const repeated = buildSummary({ id: 'repeated', requester: { name: 'María Pérez' } })
  const partial = buildSummary({ id: 'partial', requester: { name: 'MARÍA Gómez' } })
  // Campos de detalle deliberadamente presentes: no son criterios de búsqueda.
  const privateRequester = { name: 'Otra Persona', email: 'maria@example.com', id: 'maria-user' }
  const other = buildSummary({ id: 'other', requester: privateRequester })
  const absent = buildSummary({ id: 'absent' })
  delete absent.requester
  const nullRequester = buildSummary({ id: 'null', requester: null })
  const emptyName = buildSummary({ id: 'empty', requester: { name: '' } })
  const blankName = buildSummary({ id: 'blank', requester: { name: '   ' } })
  const missingName = buildSummary({ id: 'missing-name', requester: { name: '' } })
  Reflect.deleteProperty(missingName.requester!, 'name')
  const requesters = [named, repeated, partial, other, absent, nullRequester, emptyName, blankName, missingName]

  it.each([
    ['', requesters],
    ['   ', requesters],
    ['  mArÍA  ', [named, repeated, partial]],
    ['PÉR', [named, repeated]],
    ['maria', []],
    ['maria@example.com', []],
    ['maria-user', []],
    ['desconocido', []],
  ])('solicitante por nombre parcial, sin correo/ID ni quitar acentos: %j', (requester, expected) => {
    expect(filterTickets(requesters, { ...DEFAULT_TICKET_FILTERS, requester })).toEqual(expected)
  })

  const slaStates = ['en_tiempo', 'en_riesgo', 'cumplido', 'incumplido'] as const
  const withSla = slaStates.map((status) => buildSummary({
    id: status,
    // Fechas vencidas y señales contradictorias no sustituyen el snapshot de negocio.
    sla: buildSla({ status, due_at: '2000-01-01T00:00:00Z', near_due: true, breached: true }),
  }))
  const absentSla = buildSummary({ id: 'absent-sla', priority: null })
  Reflect.deleteProperty(absentSla, 'sla')
  const slaTickets = [...withSla, noPriority, absentSla]

  it.each(slaStates)('SLA exacto %s, sin agrupar por color/señal ni recalcular', (sla) => {
    expect(filterTickets(slaTickets, { ...DEFAULT_TICKET_FILTERS, sla })).toEqual([
      withSla[slaStates.indexOf(sla)],
    ])
  })

  it.each([
    ['all', slaTickets],
    ['none', [noPriority, absentSla]],
  ] as const)('SLA %s incluye solo los datos correspondientes', (sla, expected) => {
    expect(filterTickets(slaTickets, { ...DEFAULT_TICKET_FILTERS, sla })).toEqual(expected)
  })

  it('Sin SLA no se deduce de prioridad, estado vacío ni banderas', () => {
    const present = [
      buildSummary({ priority: null, sla: buildSla() }),
      buildSummary({ sla: buildSla({ status: '' }) }),
    ]
    const missing = buildSummary({ priority: 'Alta', sla: null })
    expect(filterTickets([...present, missing], { ...DEFAULT_TICKET_FILTERS, sla: 'none' })).toEqual([missing])
  })

  const combined: TicketFilters = {
    ...DEFAULT_TICKET_FILTERS,
    query: ' PORTAL ',
    status: 'Abierto',
    priority: 'Alta',
    requester: '  MARÍA ',
    assignee: 'u-tech',
    sla: 'en_tiempo',
  }
  const titleMatch = buildSummary({
    id: 'title-match',
    title: 'Acceso al portal',
    requester: { name: 'María Pérez' },
    assignee: { id: 'u-tech', name: 'Tomás Técnico' },
  })
  const idMatch = buildSummary({ ...titleMatch, id: 'PORTAL-123', title: 'Otro título' })
  const neither = buildSummary({ ...titleMatch, id: 'neither', title: 'Sin coincidencia' })
  const nearMisses = [
    buildSummary({ ...titleMatch, id: 'status', status: 'Cerrado' }),
    buildSummary({ ...titleMatch, id: 'priority', priority: 'Baja' }),
    buildSummary({ ...titleMatch, id: 'requester', requester: { name: 'Otra Persona' } }),
    buildSummary({ ...titleMatch, id: 'assignee', assignee: null }),
    buildSummary({ ...titleMatch, id: 'sla', sla: buildSla({ status: 'cumplido' }) }),
    neither,
  ]

  it('agrupa (ID O título) Y todos los criterios, sin mutar ni reordenar', () => {
    const tickets = Object.freeze([idMatch, ...nearMisses, titleMatch])
    const before = structuredClone(tickets)
    const filters = Object.freeze({ ...combined })
    const result = filterTickets(tickets, filters)
    expect(result).toEqual([idMatch, titleMatch])
    expect(result[0]).toBe(idMatch)
    expect(tickets).toEqual(before)
    expect(filters).toEqual(combined)
    expect(paginateTickets(sortTickets(result, 'recent'), 99)).toMatchObject({
      items: [idMatch, titleMatch], total: 2, pages: 1, page: 1,
    })
  })

  it.each([
    { query: '#PORTAL' },
    { query: 'portal-123' },
    { query: 'otro título' },
  ])('mantiene el OR agrupado con todos los demás filtros: %j', (patch) => {
    expect(filterTickets([idMatch, ...nearMisses, titleMatch], { ...combined, ...patch })).toEqual([idMatch])
  })

  it.each([
    { status: 'Resuelto' },
    { priority: 'Crítica' },
    { requester: 'No existe' },
    { assignee: 'otro-tecnico' },
    { sla: 'incumplido' },
  ])('cualquier criterio discordante impide la coincidencia completa: %j', (patch) => {
    expect(filterTickets([idMatch, titleMatch], { ...combined, ...patch })).toEqual([])
  })

  it('no busca en descripción, comentarios o historial aunque lleguen en el objeto', () => {
    const extended = {
      ...titleMatch,
      description: 'Secreto buscable',
      comments: [{ body: 'Secreto buscable' }],
      history: ['Secreto buscable'],
    }
    expect(filterTickets([extended], { ...DEFAULT_TICKET_FILTERS, query: 'secreto' })).toEqual([])
  })

  it('filtra antes de ordenar/paginar el subconjunto sin cambiar las reglas existentes', () => {
    const many = Array.from({ length: 24 }, (_, index) => buildSummary({
      id: `page-${index}`,
      requester: { name: index % 2 ? 'María' : 'Otra Persona' },
      created_at: `2026-11-${String(index + 1).padStart(2, '0')}T08:00:00Z`,
    }))
    const result = sortTickets(filterTickets(many, { ...DEFAULT_TICKET_FILTERS, requester: 'maría', sla: 'en_tiempo' }), 'oldest')
    expect(paginateTickets(result, 2)).toMatchObject({
      items: [many[21], many[23]], total: 12, pages: 2, page: 2, from: 11, to: 12,
    })
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
      requester: '',
      sla: 'all',
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

  it('lee y valida solicitante y SLA sin descartar los criterios válidos', () => {
    const filters = parseTicketQuery(
      new URLSearchParams(
        'q=%20portal%20&priority=Urgente&status=Abierto&assignee=u-tech&requester=%20Mar%C3%ADa%20&sla=en_riesgo&sort=oldest&page=3',
      ),
    )

    expect(filters).toEqual({
      query: 'portal',
      priority: 'all',
      status: 'Abierto',
      assignee: 'u-tech',
      requester: 'María',
      sla: 'en_riesgo',
      sort: 'oldest',
      page: 3,
    })
  })

  it.each([
    ['vencido', 'all'],
    ['NONE', 'all'],
    ['', 'all'],
    ['none', 'none'],
    ['cumplido', 'cumplido'],
  ])('normaliza solo el SLA inválido %j', (sla, expected) => {
    const filters = parseTicketQuery(
      new URLSearchParams(`requester=ana&sla=${sla}&status=Resuelto&priority=Baja`),
    )
    expect(filters).toMatchObject({
      requester: 'ana',
      sla: expected,
      status: 'Resuelto',
      priority: 'Baja',
    })
  })

  it('hace round-trip de solicitante y SLA junto a los parámetros existentes', () => {
    const filters: TicketFilters = {
      ...DEFAULT_TICKET_FILTERS,
      query: 'portal',
      status: 'Abierto',
      requester: ' María ',
      sla: 'none',
      sort: 'oldest',
      page: 2,
    }
    const params = ticketQueryToParams(filters)

    expect(params.toString()).toBe(
      'q=portal&status=Abierto&requester=Mar%C3%ADa&sla=none&sort=oldest&page=2',
    )
    expect(parseTicketQuery(params)).toEqual({ ...filters, requester: 'María' })
  })

  it.each([
    [{ requester: 'ana' }, true],
    [{ requester: '   ' }, false],
    [{ sla: 'none' }, true],
    [{ sla: 'en_tiempo' }, true],
    [{ sla: 'all' }, false],
  ])('detecta los criterios nuevos como filtros activos: %j', (patch, expected) => {
    expect(hasActiveTicketFilters({ ...DEFAULT_TICKET_FILTERS, ...patch })).toBe(
      expected,
    )
  })

  it('limpia todos los criterios con una sola operación y conserva el orden', () => {
    const dirty: TicketFilters = {
      ...DEFAULT_TICKET_FILTERS,
      query: 'portal',
      requester: ' ana ',
      sla: 'none',
      status: 'Abierto',
      priority: 'Alta',
      assignee: 'u-tech',
      sort: 'sla',
      page: 3,
    }
    const cleared = clearTicketFilters(dirty)

    expect(cleared).toEqual({ ...DEFAULT_TICKET_FILTERS, sort: 'sla' })
    expect(hasActiveTicketFilters(cleared)).toBe(false)
    expect(ticketQueryToParams(cleared).toString()).toBe('sort=sla')
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
