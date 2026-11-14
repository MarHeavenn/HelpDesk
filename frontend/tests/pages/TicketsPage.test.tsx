import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ApiError } from '@/api/httpClient'
import TicketsPage from '@/pages/TicketsPage'
import { ADMIN, renderApp } from '../helpers/renderApp'
import {
  ASSIGNEE,
  buildSla,
  buildSummary,
  createTicketsApiFake,
} from '../helpers/ticketFixtures'

const abierto = buildSummary({
  id: 't-aaaa0001',
  title: 'No puedo entrar al portal',
  priority: 'Alta',
  status: 'Abierto',
  created_at: '2026-11-10T08:00:00+00:00',
})

const cerrado = buildSummary({
  id: 't-bbbb0002',
  title: 'Solicitud de licencia',
  priority: 'Baja',
  status: 'Cerrado',
  assignee: ASSIGNEE,
  created_at: '2026-11-12T08:00:00+00:00',
  sla: buildSla({ status: 'cumplido' }),
})

const enRiesgo = buildSummary({
  id: 't-cccc0003',
  title: 'Servidor caído',
  priority: 'Crítica',
  status: 'En progreso',
  created_at: '2026-11-11T08:00:00+00:00',
  sla: buildSla({ status: 'en_riesgo', due_at: '2026-11-13T08:00:00+00:00' }),
})

function renderPage(api = createTicketsApiFake(), route = '/') {
  return renderApp(<TicketsPage api={api} />, { user: ADMIN, route })
}

describe('TicketsPage', () => {
  it('muestra todos los tickets reales con contador y datos de cada fila', async () => {
    const api = createTicketsApiFake({
      listAll: vi.fn(async () => [abierto, cerrado, enRiesgo]),
    })
    renderPage(api)

    expect(await screen.findByText('No puedo entrar al portal')).toBeVisible()
    expect(screen.getByText('Solicitud de licencia')).toBeVisible()
    expect(screen.getByText('Servidor caído')).toBeVisible()
    expect(screen.getByText('Mostrando 1–3 de 3')).toBeVisible()
    expect(screen.getByText('#T-AAAA00')).toBeVisible()
    expect(
      within(
        screen.getByText('Solicitud de licencia').closest('tr') as HTMLElement,
      ).getByText('Tomás Técnico'),
    ).toBeVisible()
    expect(api.listAll).toHaveBeenCalledTimes(1)
    expect(api.listMine).not.toHaveBeenCalled()
  })

  it('filtra por estado y por texto, y permite limpiar los filtros', async () => {
    const user = userEvent.setup()
    const api = createTicketsApiFake({
      listAll: vi.fn(async () => [abierto, cerrado, enRiesgo]),
    })
    renderPage(api)
    await screen.findByText('No puedo entrar al portal')

    await user.selectOptions(screen.getByLabelText('Estado'), 'Cerrado')
    await waitFor(() =>
      expect(screen.queryByText('No puedo entrar al portal')).not.toBeInTheDocument(),
    )
    expect(screen.getByText('Solicitud de licencia')).toBeVisible()
    expect(
      within(
        screen.getByText('Solicitud de licencia').closest('tr') as HTMLElement,
      ).getByText('Tomás Técnico'),
    ).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Limpiar filtros' }))
    expect(await screen.findByText('No puedo entrar al portal')).toBeVisible()

    await user.type(screen.getByLabelText('Buscar tickets'), 'servidor')
    await waitFor(
      () =>
        expect(
          screen.queryByText('No puedo entrar al portal'),
        ).not.toBeInTheDocument(),
      { timeout: 2000 },
    )
    expect(screen.getByText('Servidor caído')).toBeVisible()
    expect(screen.getByText('Mostrando 1–1 de 1')).toBeVisible()
  })

  it('muestra el vacío sin tickets con acción de crear', async () => {
    renderPage(createTicketsApiFake({ listAll: vi.fn(async () => []) }))

    expect(await screen.findByText('Aún no hay tickets')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Crear ticket' })).toHaveAttribute(
      'href',
      '/tickets/nuevo',
    )
  })

  it('distingue el vacío por filtros y ofrece limpiarlos', async () => {
    const user = userEvent.setup()
    renderPage(createTicketsApiFake({ listAll: vi.fn(async () => [abierto]) }))
    await screen.findByText('No puedo entrar al portal')

    await user.selectOptions(screen.getByLabelText('Prioridad'), 'Crítica')

    expect(
      await screen.findByText('No encontramos tickets con esos filtros'),
    ).toBeVisible()
    await user.click(
      screen.getAllByRole('button', { name: 'Limpiar filtros' })[0],
    )
    expect(await screen.findByText('No puedo entrar al portal')).toBeVisible()
  })

  it('muestra el error de red y reintenta la consulta', async () => {
    const user = userEvent.setup()
    const listAll = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(500, 'boom'))
      .mockResolvedValueOnce([])
    renderPage(createTicketsApiFake({ listAll }))

    expect(
      await screen.findByText('No se pudo cargar la lista de tickets'),
    ).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('Aún no hay tickets')).toBeVisible()
    expect(listAll).toHaveBeenCalledTimes(2)
  })

  it('pagina de 10 en 10 y actualiza el rango mostrado', async () => {
    const user = userEvent.setup()
    const tickets = Array.from({ length: 12 }, (_, index) =>
      buildSummary({
        id: `t-page${String(index).padStart(4, '0')}`,
        title: `Ticket ${index + 1}`,
        priority: 'Media',
      }),
    )
    renderPage(createTicketsApiFake({ listAll: vi.fn(async () => tickets) }))

    expect(await screen.findByText('Mostrando 1–10 de 12')).toBeVisible()
    expect(screen.getAllByRole('row')).toHaveLength(11)

    await user.click(screen.getByRole('button', { name: 'Página 2' }))

    expect(await screen.findByText('Mostrando 11–12 de 12')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Página 2' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('abre el detalle del ticket en un diálogo modal', async () => {
    const user = userEvent.setup()
    const api = createTicketsApiFake({
      listAll: vi.fn(async () => [abierto]),
    })
    renderPage(api)
    await screen.findByText('No puedo entrar al portal')

    await user.click(
      screen.getByRole('button', { name: 'Ver detalle del ticket #T-AAAA00' }),
    )

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    expect(
      within(dialog).getByText('Desde ayer no puedo entrar al portal.'),
    ).toBeVisible()
    expect(within(dialog).getByText('Carla Cliente · carla@example.com')).toBeVisible()
    expect(api.getTicket).toHaveBeenCalledWith('t-aaaa0001')
  })

  it('no muestra un vacío falso cuando la sesión expira (401)', async () => {
    const api = createTicketsApiFake({
      listAll: vi.fn(async () => {
        throw new ApiError(401, 'no session')
      }),
    })
    renderPage(api)

    await waitFor(() => expect(api.listAll).toHaveBeenCalled())
    expect(screen.queryByText('Aún no hay tickets')).not.toBeInTheDocument()
    expect(
      screen.queryByText('No se pudo cargar la lista de tickets'),
    ).not.toBeInTheDocument()
  })
})
