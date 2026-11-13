import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'

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
})
