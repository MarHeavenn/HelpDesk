import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { TicketsApi } from '@/api/tickets.api'
import CreateTicketPage from '@/pages/CreateTicketPage'
import { renderApp } from '../helpers/renderApp'

const created = {
  id: '12345678-aaaa-bbbb-cccc-dddddddddddd',
  title: 'Problema de acceso',
  description: 'No puedo acceder al sistema desde esta mañana',
  priority: null,
  status: 'Abierto',
  assignee: null,
  requester: null,
  sla: null,
  created_at: '2026-11-10T12:00:00+00:00',
  resolved_at: null,
  requester_id: 'u-admin',
}

function api(): TicketsApi {
  return {
    listMine: vi.fn(),
    listAssigned: vi.fn(),
    create: vi.fn(async () => created),
    get: vi.fn(),
    setPriority: vi.fn(async () => ({ ...created, priority: 'Alta' })),
    setStatus: vi.fn(),
    reopen: vi.fn(),
    assign: vi.fn(),
    listComments: vi.fn(),
    addComment: vi.fn(),
    history: vi.fn(),
  }
}

describe('CreateTicketPage', () => {
  it('valida los campos antes de crear', async () => {
    const tickets = api()
    const user = userEvent.setup()
    renderApp(<CreateTicketPage api={tickets} />)

    await user.click(screen.getByRole('button', { name: 'Crear ticket' }))

    expect(screen.getByText('Ingresa un título')).toBeInTheDocument()
    expect(screen.getByText('Ingresa una descripción')).toBeInTheDocument()
    expect(tickets.create).not.toHaveBeenCalled()
  })

  it('crea el ticket y fija prioridad para un administrador', async () => {
    const tickets = api()
    const user = userEvent.setup()
    renderApp(<CreateTicketPage api={tickets} />)

    await user.type(screen.getByLabelText('Título'), 'Problema de acceso')
    await user.type(screen.getByLabelText('Descripción'), 'No puedo acceder al sistema desde esta mañana')
    await user.selectOptions(screen.getByLabelText('Prioridad'), 'Alta')
    await user.click(screen.getByRole('button', { name: 'Crear ticket' }))

    await waitFor(() => expect(tickets.create).toHaveBeenCalledWith({
      title: 'Problema de acceso',
      description: 'No puedo acceder al sistema desde esta mañana',
    }))
    expect(tickets.setPriority).toHaveBeenCalledWith(created.id, 'Alta')
  })
})
