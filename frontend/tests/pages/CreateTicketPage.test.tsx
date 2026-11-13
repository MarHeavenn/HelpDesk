/**
 * Cobertura RF-55 (crear ticket real) con el contrato de HU-02:
 * validación 1–200 / 1–5000, alta real, prioridad para staff, SLA del
 * administrador, aviso de alta y descarte con confirmación.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ApiError } from '@/api/httpClient'
import type { TicketsApi } from '@/api/tickets.api'
import { AuthProvider } from '@/context/AuthContext'
import CreateTicketPage from '@/pages/CreateTicketPage'
import CreatedTicketNotice from '@/pages/CreatedTicketNotice'
import type { Ticket } from '@/types/ticket'
import { ADMIN, CLIENTE, TECNICO, createAuthApi } from '../helpers/renderApp'

const ticket: Ticket = {
  id: 't-1',
  title: 'No puedo entrar',
  description: 'Desde ayer no puedo entrar al portal.',
  priority: null,
  status: 'Abierto',
  created_at: '2026-11-10T00:00:00Z',
  requester_id: 'u-admin',
}

function fakeTicketsApi(overrides: Partial<TicketsApi> = {}): TicketsApi {
  return {
    createTicket: vi.fn(async () => ticket),
    listMine: vi.fn(async () => []),
    listAssigned: vi.fn(async () => []),
    listAll: vi.fn(async () => []),
    getTicket: vi.fn(async () => ({
      ...ticket,
      assignee: null,
      requester: null,
      sla: null,
    })),
    setStatus: vi.fn(async () => ticket),
    assign: vi.fn(async () => ticket),
    listTechnicians: vi.fn(async () => []),
    listComments: vi.fn(async () => []),
    addComment: vi.fn(async () => ({
      id: 'c-1',
      ticket_id: ticket.id,
      body: 'Comentario',
      author: null,
      created_at: ticket.created_at,
    })),
    setPriority: vi.fn(async () => ({ ...ticket, priority: 'Alta' })),
    getSlaPolicies: vi.fn(async () => [
      { priority: 'Crítica', hours: 120 },
      { priority: 'Alta', hours: 240 },
      { priority: 'Media', hours: 720 },
      { priority: 'Baja', hours: 1440 },
    ]),
    ...overrides,
  }
}

function renderPage({
  user = ADMIN,
  api = fakeTicketsApi(),
}: {
  user?: typeof ADMIN
  api?: TicketsApi
} = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider api={createAuthApi(user)}>
        <MemoryRouter initialEntries={['/tickets/nuevo']}>
          <Routes>
            <Route
              path="/mis-tickets"
              element={
                <>
                  <CreatedTicketNotice />
                  <p>mis tickets</p>
                </>
              }
            />
            <Route path="/" element={<p>inicio</p>} />
            <Route
              path="/tickets/nuevo"
              element={<CreateTicketPage api={api} />}
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    await screen.findByLabelText('Título del ticket'),
    'No puedo entrar',
  )
  await user.type(
    screen.getByLabelText('Descripción del problema'),
    'Desde ayer no puedo entrar al portal.',
  )
}

afterEach(() => {
  localStorage.clear()
})

describe('CreateTicketPage', () => {
  it('muestra el SLA vigente de la prioridad por defecto al administrador', async () => {
    const api = fakeTicketsApi()
    renderPage({ api })

    expect(
      await screen.findByText(
        'Tiempo objetivo para prioridad media: 720 horas',
      ),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Prioridad')).toHaveValue('Media')
    expect(api.getSlaPolicies).toHaveBeenCalledTimes(1)
  })

  it('valida los campos obligatorios y enfoca el primer error', async () => {
    const api = fakeTicketsApi()
    renderPage({ api })
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Crear ticket' }))

    expect(screen.getByText('El título es obligatorio.')).toBeInTheDocument()
    expect(screen.getByText('La descripción es obligatoria.')).toBeInTheDocument()
    expect(screen.getByLabelText('Título del ticket')).toHaveFocus()
    expect(api.createTicket).not.toHaveBeenCalled()
  })

  it('rechaza un título de más de 200 caracteres', async () => {
    const api = fakeTicketsApi()
    renderPage({ api })
    const user = userEvent.setup()

    fireEvent.change(await screen.findByLabelText('Título del ticket'), {
      target: { value: 'a'.repeat(201) },
    })
    fireEvent.change(screen.getByLabelText('Descripción del problema'), {
      target: { value: 'Descripción válida' },
    })
    await user.click(screen.getByRole('button', { name: 'Crear ticket' }))

    expect(
      screen.getByText('El título admite como máximo 200 caracteres.'),
    ).toBeInTheDocument()
    expect(api.createTicket).not.toHaveBeenCalled()
  })

  it('crea el ticket, fija la prioridad y avisa en Mis tickets', async () => {
    const api = fakeTicketsApi()
    renderPage({ api })
    const user = userEvent.setup()

    await fillValidForm(user)
    await user.selectOptions(screen.getByLabelText('Prioridad'), 'Alta')
    await user.click(screen.getByRole('button', { name: 'Crear ticket' }))

    await waitFor(() =>
      expect(api.createTicket).toHaveBeenCalledWith({
        title: 'No puedo entrar',
        description: 'Desde ayer no puedo entrar al portal.',
      }),
    )
    expect(api.setPriority).toHaveBeenCalledWith('t-1', 'Alta')
    expect(
      await screen.findByText('Ticket creado. Identificador t-1.'),
    ).toBeInTheDocument()
    expect(screen.getByText('mis tickets')).toBeInTheDocument()
  })

  it('avisa si el ticket se creó pero la prioridad falló', async () => {
    const api = fakeTicketsApi({
      setPriority: vi.fn(async () => {
        throw new ApiError(422, 'prioridad no permitida')
      }),
    })
    renderPage({ api })
    const user = userEvent.setup()

    await fillValidForm(user)
    await user.click(screen.getByRole('button', { name: 'Crear ticket' }))

    expect(
      await screen.findByText(
        /El ticket t-1 se creó, pero no se pudo guardar la prioridad\./,
      ),
    ).toBeInTheDocument()
  })

  it('crea el ticket del cliente sin prioridad ni consulta de SLA', async () => {
    const api = fakeTicketsApi()
    renderPage({ api, user: CLIENTE })
    const user = userEvent.setup()

    await fillValidForm(user)

    expect(screen.queryByLabelText('Prioridad')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Crear ticket' }))

    await waitFor(() => expect(api.createTicket).toHaveBeenCalledTimes(1))
    expect(api.setPriority).not.toHaveBeenCalled()
    expect(api.getSlaPolicies).not.toHaveBeenCalled()
    expect(
      await screen.findByText('Ticket creado. Identificador t-1.'),
    ).toBeInTheDocument()
  })

  it('muestra la prioridad al técnico sin consultar la política de SLA', async () => {
    const api = fakeTicketsApi()
    renderPage({ api, user: TECNICO })

    expect(await screen.findByLabelText('Prioridad')).toBeInTheDocument()
    expect(api.getSlaPolicies).not.toHaveBeenCalled()
    expect(
      screen.queryByText('Consultando el tiempo objetivo de SLA...'),
    ).not.toBeInTheDocument()
  })

  it('muestra el error de red y permite reintentar', async () => {
    const api = fakeTicketsApi({
      createTicket: vi.fn(async () => {
        throw new Error('sin conexión')
      }),
    })
    renderPage({ api })
    const user = userEvent.setup()

    await fillValidForm(user)
    await user.click(screen.getByRole('button', { name: 'Crear ticket' }))

    expect(
      await screen.findByText(
        'No se pudo crear el ticket. Revisa tu conexión e inténtalo de nuevo.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Crear ticket' })).toBeEnabled()
  })

  it('pide confirmación al cancelar con cambios', async () => {
    renderPage()
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Título del ticket'), 'Algo')
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(
      screen.getByRole('alertdialog', { name: '¿Descartar el ticket?' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Seguir editando' }))
    expect(
      screen.queryByRole('alertdialog', { name: '¿Descartar el ticket?' }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    await user.click(screen.getByRole('button', { name: 'Descartar' }))

    expect(await screen.findByText('inicio')).toBeInTheDocument()
  })

  it('cancela sin confirmación cuando no hay cambios', async () => {
    renderPage()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Cancelar' }))

    expect(await screen.findByText('inicio')).toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })
})
