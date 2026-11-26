import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import MyTicketsPage from '@/pages/MyTicketsPage'
import TicketsPage from '@/pages/TicketsPage'
import { ADMIN, CLIENTE, SUPERVISOR, renderApp } from '../helpers/renderApp'
import {
  ASSIGNEE,
  buildSla,
  buildSummary,
  createTicketsApiFake,
} from '../helpers/ticketFixtures'

const mariaRiesgo = buildSummary({
  id: 't-hu17a001',
  title: 'Acceso al portal',
  status: 'Abierto',
  requester: { name: 'María Pérez' },
  sla: buildSla({ status: 'en_riesgo' }),
  created_at: '2026-11-10T08:00:00+00:00',
})

const mariaCumplido = buildSummary({
  id: 't-hu17a002',
  title: 'Licencia solicitada',
  status: 'Abierto',
  requester: { name: 'María Gómez' },
  sla: buildSla({ status: 'cumplido' }),
  created_at: '2026-11-11T08:00:00+00:00',
})

const otraRiesgo = buildSummary({
  id: 't-hu17a003',
  title: 'Servidor caído',
  status: 'Abierto',
  requester: { name: 'Otra Persona' },
  sla: buildSla({ status: 'en_riesgo' }),
  created_at: '2026-11-12T08:00:00+00:00',
})

describe('TicketListPage HU-17: criterios, roles y vacíos', () => {
  it('la base vacía prevalece aunque haya filtros activos', async () => {
    renderApp(
      <TicketsPage
        api={createTicketsApiFake({ listAll: vi.fn(async () => []) })}
      />,
      { user: ADMIN, route: '/?requester=ana&sla=none' },
    )

    expect(await screen.findByText('Aún no hay tickets')).toBeVisible()
    expect(
      screen.queryByText('No encontramos tickets con esos filtros'),
    ).not.toBeInTheDocument()
  })

  it('solo una base no vacía muestra «No hay coincidencias» y limpia todo', async () => {
    const user = userEvent.setup()
    renderApp(
      <TicketsPage
        api={createTicketsApiFake({
          listAll: vi.fn(async () => [mariaRiesgo, otraRiesgo]),
        })}
      />,
      { user: ADMIN, route: '/?requester=Nadie&sla=cumplido' },
    )

    expect(
      await screen.findByText('No encontramos tickets con esos filtros'),
    ).toBeVisible()
    expect(screen.getByLabelText('Solicitante')).toHaveValue('Nadie')
    expect(screen.getByLabelText('Estado del SLA')).toHaveValue('cumplido')

    const buttons = screen.getAllByRole('button', { name: 'Limpiar filtros' })
    await user.click(buttons[buttons.length - 1])

    expect(await screen.findByText('Acceso al portal')).toBeVisible()
    expect(screen.getByText('Servidor caído')).toBeVisible()
    expect(screen.getByLabelText('Solicitante')).toHaveValue('')
    expect(screen.getByLabelText('Estado del SLA')).toHaveValue('all')
    expect(screen.getByText('Mostrando 1–2 de 2')).toBeVisible()
  })

  it('combina solicitante y SLA con el resto de criterios', async () => {
    renderApp(
      <TicketsPage
        api={createTicketsApiFake({
          listAll: vi.fn(async () => [
            mariaRiesgo,
            mariaCumplido,
            otraRiesgo,
          ]),
        })}
      />,
      { user: ADMIN, route: '/?requester=mar&sla=en_riesgo' },
    )

    expect(await screen.findByText('Acceso al portal')).toBeVisible()
    await waitFor(() =>
      expect(screen.queryByText('Licencia solicitada')).not.toBeInTheDocument(),
    )
    expect(screen.queryByText('Servidor caído')).not.toBeInTheDocument()
    expect(screen.getByText('Mostrando 1–1 de 1')).toBeVisible()
  })

  it('el cliente ignora un filtro de técnico forzado por URL', async () => {
    const asignadoAOtro = buildSummary({
      id: 't-hu17b001',
      title: 'Asignado a otro técnico',
      assignee: ASSIGNEE,
    })
    const sinAsignar = buildSummary({
      id: 't-hu17b002',
      title: 'Ticket sin técnico',
      assignee: null,
    })
    renderApp(
      <MyTicketsPage
        api={createTicketsApiFake({
          listMine: vi.fn(async () => [asignadoAOtro, sinAsignar]),
        })}
      />,
      { user: CLIENTE, route: '/?assignee=u-tech' },
    )

    expect(await screen.findByText('Asignado a otro técnico')).toBeVisible()
    expect(screen.getByText('Ticket sin técnico')).toBeVisible()
    expect(screen.getByText('Mostrando 1–2 de 2')).toBeVisible()
    expect(screen.queryByLabelText('Técnico')).not.toBeInTheDocument()
  })

  it('el supervisor carga la vista general e ignora un técnico forzado', async () => {
    renderApp(
      <TicketsPage
        api={createTicketsApiFake({
          listAll: vi.fn(async () => [mariaRiesgo, otraRiesgo]),
        })}
      />,
      { user: SUPERVISOR, route: '/?assignee=u-tech' },
    )

    expect(await screen.findByText('Acceso al portal')).toBeVisible()
    expect(screen.getByText('Servidor caído')).toBeVisible()
    expect(screen.getByText('Mostrando 1–2 de 2')).toBeVisible()
    expect(screen.queryByLabelText('Técnico')).not.toBeInTheDocument()
  })

  it('normaliza una página fuera de rango sobre el subconjunto filtrado', async () => {
    const abiertos = Array.from({ length: 12 }, (_, index) =>
      buildSummary({
        id: `t-hu17c${String(index).padStart(3, '0')}`,
        title: `Abierto ${index + 1}`,
        status: 'Abierto',
        priority: 'Media',
      }),
    )
    const cerrados = Array.from({ length: 3 }, (_, index) =>
      buildSummary({
        id: `t-hu17d${String(index).padStart(3, '0')}`,
        title: `Cerrado ${index + 1}`,
        status: 'Cerrado',
        priority: 'Media',
      }),
    )
    renderApp(
      <TicketsPage
        api={createTicketsApiFake({
          listAll: vi.fn(async () => [...abiertos, ...cerrados]),
        })}
      />,
      { user: ADMIN, route: '/?status=Abierto&page=99' },
    )

    expect(await screen.findByText('Mostrando 1–10 de 12')).toBeVisible()
    expect(screen.getAllByRole('row')).toHaveLength(11)
    expect(screen.queryByText('Cerrado 1')).not.toBeInTheDocument()
  })
})
