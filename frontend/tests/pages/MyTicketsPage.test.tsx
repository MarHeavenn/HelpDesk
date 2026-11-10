import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import type { TicketsApi } from '@/api/tickets.api'
import type { TechniciansApi } from '@/api/technicians.api'
import MyTicketsPage from '@/pages/MyTicketsPage'
import { renderApp, TECNICO } from '../helpers/renderApp'

const ticket = {
  id: '12345678-aaaa-bbbb-cccc-dddddddddddd',
  title: 'No puedo entrar al portal',
  priority: 'Alta',
  status: 'Abierto',
  assignee: null,
  sla: null,
  created_at: '2026-11-10T12:00:00+00:00',
}

function api(overrides: Partial<TicketsApi> = {}): TicketsApi {
  return {
    listMine: vi.fn(async () => [ticket]),
    listAssigned: vi.fn(async () => [ticket]),
    create: vi.fn(),
    get: vi.fn(),
    setPriority: vi.fn(),
    setStatus: vi.fn(),
    reopen: vi.fn(),
    assign: vi.fn(),
    listComments: vi.fn(),
    addComment: vi.fn(),
    history: vi.fn(),
    ...overrides,
  }
}

function directory(): TechniciansApi {
  return { list: vi.fn(async () => [{ id: 'tech-1', name: 'Técnico Demo' }]) }
}

describe('MyTicketsPage', () => {
  it('carga tickets propios para un administrador', async () => {
    const tickets = api()
    renderApp(<MyTicketsPage api={tickets} />)

    expect(await screen.findByText('No puedo entrar al portal')).toBeInTheDocument()
    expect(tickets.listMine).toHaveBeenCalledTimes(1)
    expect(tickets.listAssigned).not.toHaveBeenCalled()
    expect(screen.getByText('TCK-123456')).toBeInTheDocument()
  })

  it('carga tickets asignados para un técnico', async () => {
    const tickets = api()
    renderApp(<MyTicketsPage api={tickets} />, { user: TECNICO })

    expect(await screen.findByText('No puedo entrar al portal')).toBeInTheDocument()
    expect(tickets.listAssigned).toHaveBeenCalledTimes(1)
    expect(tickets.listMine).not.toHaveBeenCalled()
    expect(screen.getByText('Tickets asignados para tu atención')).toBeInTheDocument()
  })

  it('muestra el estado vacío y permite reintentar ante error', async () => {
    const tickets = api({ listMine: vi.fn(async () => []) })
    renderApp(<MyTicketsPage api={tickets} />)

    await waitFor(() => expect(screen.getByText('Aún no tienes tickets')).toBeInTheDocument())
    expect(screen.getAllByText('+ Crear ticket')).toHaveLength(2)
  })

  it('abre el detalle y permite actualizar el estado', async () => {
    const tickets = api({
      get: vi.fn(async () => ({ ...ticket, description: 'Descripción completa del ticket', requester: null, resolved_at: null, requester_id: 'u-admin' })),
      listComments: vi.fn(async () => []),
      history: vi.fn(async () => []),
      setStatus: vi.fn(async () => ({ ...ticket, status: 'En progreso', description: 'Descripción completa del ticket', requester: null, resolved_at: null, requester_id: 'u-admin' })),
    })
    const user = (await import('@testing-library/user-event')).default.setup()
    renderApp(<MyTicketsPage api={tickets} directory={directory()} />)

    await user.click(await screen.findByRole('button', { name: 'Ver detalle de TCK-123456' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Estado'), 'En progreso')

    await waitFor(() => expect(tickets.setStatus).toHaveBeenCalledWith(ticket.id, 'En progreso'))
  })
})
