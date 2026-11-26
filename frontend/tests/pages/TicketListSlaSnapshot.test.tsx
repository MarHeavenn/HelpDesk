import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'

import TicketsPage from '@/pages/TicketsPage'
import { ticketKeys } from '@/hooks/useTickets'
import { ADMIN, createQueryClient, renderApp } from '../helpers/renderApp'
import {
  buildSla,
  buildSummary,
  createTicketsApiFake,
} from '../helpers/ticketFixtures'

const EN_RIESGO_ID = 't-sla00002'

const TICKETS = [
  buildSummary({
    id: 't-sla00001',
    title: 'Ticket en tiempo',
    sla: buildSla({ status: 'en_tiempo', near_due: false, breached: false }),
  }),
  buildSummary({
    id: EN_RIESGO_ID,
    title: 'Ticket en riesgo',
    sla: buildSla({
      status: 'en_riesgo',
      near_due: true,
      breached: false,
      remaining_minutes: 10,
    }),
  }),
  buildSummary({
    id: 't-sla00003',
    title: 'Ticket cumplido',
    sla: buildSla({ status: 'cumplido', near_due: false, breached: false }),
  }),
  buildSummary({
    id: 't-sla00004',
    title: 'Ticket incumplido',
    sla: buildSla({
      status: 'incumplido',
      near_due: false,
      breached: true,
      remaining_minutes: 0,
    }),
  }),
  buildSummary({
    id: 't-sla00005',
    title: 'Ticket sin SLA',
    priority: null,
    sla: null,
  }),
]

function table() {
  return within(screen.getByRole('table'))
}

describe('snapshot de SLA del listado', () => {
  it('presenta los cinco estados del resumen sin pedir el detalle por fila', async () => {
    const api = createTicketsApiFake({ listAll: vi.fn(async () => [...TICKETS]) })
    renderApp(<TicketsPage api={api} />, { user: ADMIN })

    expect(await screen.findByText('Ticket en tiempo')).toBeVisible()
    expect(table().getByText('En tiempo')).toBeVisible()
    expect(table().getByText('Próximo a vencer')).toBeVisible()
    expect(table().getByText('Cumplido')).toBeVisible()
    expect(table().getByText('Vencido')).toBeVisible()
    expect(table().getByText('Sin SLA')).toBeVisible()

    expect(api.listAll).toHaveBeenCalledTimes(1)
    expect(api.getTicket).not.toHaveBeenCalled()
    expect(api.listTechnicians).not.toHaveBeenCalled()
  })

  it('actualiza el SLA solo cuando la consulta existente vuelve a responder', async () => {
    let payload = [...TICKETS]
    const listAll = vi.fn(async () => [...payload])
    const api = createTicketsApiFake({ listAll })
    const queryClient = createQueryClient()
    renderApp(<TicketsPage api={api} />, { user: ADMIN, queryClient })

    expect(await screen.findByText('Ticket en riesgo')).toBeVisible()
    expect(table().getByText('Próximo a vencer')).toBeVisible()

    const [query] = queryClient.getQueryCache().getAll()
    expect(query.observers[0].options.refetchInterval).toBeUndefined()

    payload = payload.map((ticket) =>
      ticket.id === EN_RIESGO_ID
        ? {
            ...ticket,
            sla: buildSla({ status: 'cumplido', near_due: false, breached: false }),
          }
        : ticket,
    )
    await queryClient.refetchQueries({ queryKey: ticketKeys.list('all') })

    await waitFor(() =>
      expect(table().queryByText('Próximo a vencer')).not.toBeInTheDocument(),
    )
    expect(table().getAllByText('Cumplido')).toHaveLength(2)
    expect(api.listAll).toHaveBeenCalledTimes(2)
    expect(api.getTicket).not.toHaveBeenCalled()
  })
})
