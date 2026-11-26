import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ApiError } from '@/api/httpClient'
import MyTicketsPage from '@/pages/MyTicketsPage'
import { ADMIN, CLIENTE, TECNICO, renderApp } from '../helpers/renderApp'
import { buildSummary, createTicketsApiFake } from '../helpers/ticketFixtures'

const mine = buildSummary({ id: 't-mine0001', title: 'Ticket creado por mí' })
const assigned = buildSummary({
  id: 't-assign1',
  title: 'Ticket asignado a mí',
})

describe('MyTicketsPage', () => {
  it('el técnico consulta sus tickets asignados', async () => {
    const api = createTicketsApiFake({
      listAssigned: vi.fn(async () => [assigned]),
      listMine: vi.fn(async () => [mine]),
      listAll: vi.fn(async () => [mine, assigned]),
    })
    renderApp(<MyTicketsPage api={api} />, { user: TECNICO })

    expect(
      await screen.findByText('Ticket asignado a mí'),
    ).toBeVisible()
    expect(screen.queryByText('Ticket creado por mí')).not.toBeInTheDocument()
    expect(api.listAssigned).toHaveBeenCalled()
    expect(api.listMine).not.toHaveBeenCalled()
    expect(api.listAll).not.toHaveBeenCalled()
    expect(
      screen.getByText('Tickets que tienes asignados.'),
    ).toBeVisible()
  })

  it('el cliente consulta solo los tickets que creó y no ve el filtro de técnico', async () => {
    const api = createTicketsApiFake({
      listMine: vi.fn(async () => [mine]),
      listAssigned: vi.fn(async () => [assigned]),
      listAll: vi.fn(async () => [mine, assigned]),
    })
    renderApp(<MyTicketsPage api={api} />, { user: CLIENTE })

    expect(await screen.findByText('Ticket creado por mí')).toBeVisible()
    expect(screen.queryByText('Ticket asignado a mí')).not.toBeInTheDocument()
    expect(api.listMine).toHaveBeenCalled()
    expect(api.listAssigned).not.toHaveBeenCalled()
    expect(api.listAll).not.toHaveBeenCalled()
    expect(screen.queryByLabelText('Técnico')).not.toBeInTheDocument()
    expect(screen.getByText('Solicitudes que has creado.')).toBeVisible()
  })

  it('el administrador consulta sus propios tickets, no el listado global', async () => {
    const api = createTicketsApiFake({
      listMine: vi.fn(async () => [mine]),
      listAssigned: vi.fn(async () => [assigned]),
      listAll: vi.fn(async () => [mine, assigned]),
    })
    renderApp(<MyTicketsPage api={api} />, { user: ADMIN })

    expect(await screen.findByText('Ticket creado por mí')).toBeVisible()
    expect(api.listMine).toHaveBeenCalled()
    expect(api.listAll).not.toHaveBeenCalled()
    expect(screen.getByText('Tickets que has creado.')).toBeVisible()
    expect(screen.getByLabelText('Técnico')).toBeInTheDocument()
  })

  it('muestra el error de red y reintenta la consulta propia', async () => {
    const user = userEvent.setup()
    const listMine = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(500, 'boom'))
      .mockResolvedValueOnce([mine])
    renderApp(<MyTicketsPage api={createTicketsApiFake({ listMine })} />, {
      user: CLIENTE,
    })

    expect(
      await screen.findByText('No se pudo cargar la lista de tickets'),
    ).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('Ticket creado por mí')).toBeVisible()
    expect(listMine).toHaveBeenCalledTimes(2)
  })

  it('no muestra un vacío falso cuando la sesión expira (401)', async () => {
    const api = createTicketsApiFake({
      listMine: vi.fn(async () => {
        throw new ApiError(401, 'no session')
      }),
    })
    renderApp(<MyTicketsPage api={api} />, { user: CLIENTE })

    await waitFor(() =>
      expect(
        screen.queryByRole('status', { name: 'Cargando tickets' }),
      ).not.toBeInTheDocument(),
    )
    expect(screen.queryByText('Aún no hay tickets')).not.toBeInTheDocument()
    expect(
      screen.queryByText('No se pudo cargar la lista de tickets'),
    ).not.toBeInTheDocument()
  })

  it('abre el detalle de un ticket propio en un diálogo modal', async () => {
    const user = userEvent.setup()
    const api = createTicketsApiFake({
      listMine: vi.fn(async () => [mine]),
    })
    renderApp(<MyTicketsPage api={api} />, { user: CLIENTE })
    await screen.findByText('Ticket creado por mí')

    await user.click(
      screen.getByRole('button', {
        name: 'Ver detalle del ticket #T-MINE00',
      }),
    )

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    expect(
      within(dialog).getByText('Desde ayer no puedo entrar al portal.'),
    ).toBeVisible()
    expect(api.getTicket).toHaveBeenCalledWith('t-mine0001')
  })
})
