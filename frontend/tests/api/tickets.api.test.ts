import { describe, expect, it, vi } from 'vitest'

import { createTicketsApi, type TicketsApi } from '@/api/tickets.api'

function requestMock(): Parameters<typeof createTicketsApi>[0] {
  return vi.fn() as unknown as Parameters<typeof createTicketsApi>[0]
}

describe('tickets.api', () => {
  it('consulta los tickets propios y asignados', async () => {
    const http = requestMock()
    vi.mocked(http)!.mockResolvedValue([])
    const api = createTicketsApi(http)

    await api.listMine()
    await api.listAssigned()

    expect(http).toHaveBeenNthCalledWith(1, '/api/tickets')
    expect(http).toHaveBeenNthCalledWith(2, '/api/assignments/mine')
  })

  it('crea y actualiza un ticket con los contratos reales', async () => {
    const http = requestMock()
    vi.mocked(http)!.mockResolvedValue({})
    const api: TicketsApi = createTicketsApi(http)

    await api.create({ title: 'Problema de acceso', description: 'No puedo acceder al sistema' })
    await api.setPriority('ticket-1', 'Alta')
    await api.setStatus('ticket-1', 'En progreso')
    await api.assign('ticket-1', 'tech-1')

    expect(http).toHaveBeenNthCalledWith(1, '/api/tickets', {
      method: 'POST',
      body: { title: 'Problema de acceso', description: 'No puedo acceder al sistema' },
    })
    expect(http).toHaveBeenNthCalledWith(2, '/api/tickets/ticket-1/priority', {
      method: 'PUT',
      body: { priority: 'Alta' },
    })
    expect(http).toHaveBeenNthCalledWith(3, '/api/tickets/ticket-1/status', {
      method: 'PUT',
      body: { status: 'En progreso' },
    })
    expect(http).toHaveBeenNthCalledWith(4, '/api/tickets/ticket-1/assignee', {
      method: 'PUT',
      body: { assignee_id: 'tech-1' },
    })
  })

  it('expone comentarios e historial del ticket', async () => {
    const http = requestMock()
    vi.mocked(http)!.mockResolvedValue([])
    const api = createTicketsApi(http)

    await api.listComments('ticket-1')
    await api.addComment('ticket-1', 'Actualización realizada')
    await api.history('ticket-1')

    expect(http).toHaveBeenNthCalledWith(1, '/api/tickets/ticket-1/comments')
    expect(http).toHaveBeenNthCalledWith(2, '/api/tickets/ticket-1/comments', {
      method: 'POST',
      body: { body: 'Actualización realizada' },
    })
    expect(http).toHaveBeenNthCalledWith(3, '/api/tickets/ticket-1/history')
  })
})
