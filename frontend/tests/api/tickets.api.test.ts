import { describe, expect, it, vi } from 'vitest'

import { createTicketsApi, type RequestFn } from '@/api/tickets.api'

function httpMock(payload: unknown = {}): RequestFn {
  return vi.fn(async () => payload) as unknown as RequestFn
}

describe('tickets.api', () => {
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
