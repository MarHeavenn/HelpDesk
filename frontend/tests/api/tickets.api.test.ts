import { describe, expect, expectTypeOf, it, vi } from 'vitest'

import { createTicketsApi, type RequestFn } from '@/api/tickets.api'
import type { TicketRequester, TicketSummary } from '@/types/ticket'

function httpMock(payload: unknown = {}): RequestFn {
  return vi.fn(async () => payload) as unknown as RequestFn
}

describe('tickets.api', () => {
  const summary = {
    id: 'ticket-1',
    title: 'No puedo entrar al portal',
    priority: 'Alta',
    status: 'Abierto',
    assignee: { id: 'tech-1', name: 'Ana Técnica' },
    sla: {
      target_minutes: 240,
      started_at: '2026-11-22T08:00:00+00:00',
      due_at: '2026-11-22T12:00:00+00:00',
      elapsed_minutes: 60,
      remaining_minutes: 180,
      status: 'en_tiempo',
      near_due: false,
      breached: false,
    },
    created_at: '2026-11-22T08:00:00+00:00',
  }

  it('tipa el solicitante mínimo opcional sin cambiar el solicitante del detalle', () => {
    expectTypeOf<TicketSummary['requester']>().toEqualTypeOf<
      { name: string } | null | undefined
    >()
    expectTypeOf<TicketRequester>().toEqualTypeOf<{
      id: string
      name: string
      email: string
    }>()
  })

  describe.each([
    ['listAll', '/api/tickets/all'],
    ['listMine', '/api/tickets'],
    ['listAssigned', '/api/assignments/mine'],
  ] as const)('%s', (method, path) => {
    it.each([
      ['nombre', { ...summary, requester: { name: 'Carla Cliente' } }],
      ['nulo', { ...summary, requester: null }],
      ['ausente (respuesta anterior)', { ...summary }],
    ])('conserva el resumen con solicitante %s sin peticiones adicionales', async (_, row) => {
      // Dos filas permiten detectar también un intento de completar cada detalle.
      const payload = [row, { ...row, id: 'ticket-2' }]
      const http = httpMock(payload)
      const api = createTicketsApi(http)

      const result = await api[method]()

      expect(result).toBe(payload)
      expect(result).toEqual(payload)
      expect('requester' in result[0]).toBe('requester' in row)
      expect(http).toHaveBeenCalledTimes(1)
      expect(http).toHaveBeenCalledWith(path)
    })
  })

  it('consulta los tres alcances del listado', async () => {
    const http = httpMock([])
    const api = createTicketsApi(http)

    await api.listMine()
    await api.listAssigned()
    await api.listAll()

    expect(http).toHaveBeenNthCalledWith(1, '/api/tickets')
    expect(http).toHaveBeenNthCalledWith(2, '/api/assignments/mine')
    expect(http).toHaveBeenNthCalledWith(3, '/api/tickets/all')
  })

  it('consulta el detalle y los comentarios codificando el identificador', async () => {
    const http = httpMock({})
    const api = createTicketsApi(http)

    await api.getTicket('a/b')
    await api.listComments('a/b')

    expect(http).toHaveBeenNthCalledWith(1, '/api/tickets/a%2Fb')
    expect(http).toHaveBeenNthCalledWith(2, '/api/tickets/a%2Fb/comments')
  })

  it('envía los cuerpos exactos de prioridad, estado, asignación y comentario', async () => {
    const http = httpMock({})
    const api = createTicketsApi(http)

    await api.setPriority('t-1', 'Alta')
    await api.setStatus('t-1', 'En progreso')
    await api.assign('t-1', 'u-tech')
    await api.addComment('t-1', 'Revisando el caso')

    expect(http).toHaveBeenNthCalledWith(1, '/api/tickets/t-1/priority', {
      method: 'PUT',
      body: { priority: 'Alta' },
    })
    expect(http).toHaveBeenNthCalledWith(2, '/api/tickets/t-1/status', {
      method: 'PUT',
      body: { status: 'En progreso' },
    })
    expect(http).toHaveBeenNthCalledWith(3, '/api/tickets/t-1/assignee', {
      method: 'PUT',
      body: { assignee_id: 'u-tech' },
    })
    expect(http).toHaveBeenNthCalledWith(4, '/api/tickets/t-1/comments', {
      method: 'POST',
      body: { body: 'Revisando el caso' },
    })
  })

  it('crea tickets, lista técnicos y lee las políticas de SLA', async () => {
    const http = httpMock({})
    const api = createTicketsApi(http)

    await api.createTicket({ title: 'Título', description: 'Detalle' })
    await api.listTechnicians()
    await api.getSlaPolicies()

    expect(http).toHaveBeenNthCalledWith(1, '/api/tickets', {
      method: 'POST',
      body: { title: 'Título', description: 'Detalle' },
    })
    expect(http).toHaveBeenNthCalledWith(2, '/api/technicians')
    expect(http).toHaveBeenNthCalledWith(3, '/api/sla/policies')
  })
})
