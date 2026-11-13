import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ApiError } from '@/api/httpClient'
import TicketDetailModal from '@/components/tickets/TicketDetailModal'
import { ADMIN, CLIENTE, TECNICO, renderApp } from '../helpers/renderApp'
import {
  ASSIGNEE,
  buildComment,
  buildTicket,
  createTicketsApiFake,
} from '../helpers/ticketFixtures'

const TICKET_ID = 't-00000001'

function renderModal(
  api = createTicketsApiFake(),
  user = ADMIN,
  onClose = vi.fn(),
) {
  return {
    onClose,
    ...renderApp(
      <TicketDetailModal ticketId={TICKET_ID} onClose={onClose} api={api} />,
      { user },
    ),
  }
}

describe('TicketDetailModal', () => {
  it('muestra el detalle completo y las acciones del administrador', async () => {
    const api = createTicketsApiFake({
      getTicket: vi.fn(async () =>
        buildTicket({ assignee: ASSIGNEE, status: 'Abierto' }),
      ),
      listComments: vi.fn(async () => [buildComment()]),
    })
    renderModal(api)

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    expect(
      within(dialog).getByRole('heading', { name: 'No puedo entrar al portal' }),
    ).toBeVisible()
    expect(
      within(dialog).getByText('Desde ayer no puedo entrar al portal.'),
    ).toBeVisible()
    expect(
      within(dialog).getByText('Carla Cliente · carla@example.com'),
    ).toBeVisible()
    expect(within(dialog).getByText('Objetivo: 12 horas')).toBeVisible()
    expect(within(dialog).getByText('Restan 660 min')).toBeVisible()
    expect(within(dialog).getByText('Estamos revisando el caso.')).toBeVisible()
    expect(within(dialog).getByText('Acciones')).toBeVisible()
    expect(within(dialog).getByLabelText('Cambiar estado')).toBeVisible()
    expect(within(dialog).getByLabelText('Cambiar prioridad')).toBeVisible()
    expect(within(dialog).getByLabelText('Asignar técnico')).toBeVisible()
    expect(within(dialog).getByLabelText('Nuevo comentario')).toBeVisible()
  })

  it('el cliente solo lectura: sin acciones ni formulario de comentario', async () => {
    const api = createTicketsApiFake({
      getTicket: vi.fn(async () => buildTicket()),
      listComments: vi.fn(async () => [buildComment()]),
    })
    renderModal(api, CLIENTE)

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    await within(dialog).findByText('Estamos revisando el caso.')
    expect(within(dialog).queryByText('Acciones')).not.toBeInTheDocument()
    expect(
      within(dialog).queryByLabelText('Cambiar estado'),
    ).not.toBeInTheDocument()
    expect(
      within(dialog).queryByLabelText('Nuevo comentario'),
    ).not.toBeInTheDocument()
    expect(api.listTechnicians).not.toHaveBeenCalled()
  })

  it('cambia el estado con el flujo permitido de HU-08', async () => {
    const user = userEvent.setup()
    const setStatus = vi.fn(async () => buildTicket({ status: 'En progreso' }))
    const api = createTicketsApiFake({ setStatus })
    renderModal(api)

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    await user.selectOptions(
      within(dialog).getByLabelText('Cambiar estado'),
      'En progreso',
    )
    await user.click(
      within(dialog).getByRole('button', { name: 'Cambiar estado' }),
    )

    await waitFor(() =>
      expect(setStatus).toHaveBeenCalledWith(TICKET_ID, 'En progreso'),
    )
    expect(await within(dialog).findByText('Cambios guardados.')).toBeVisible()
  })

  it('muestra el 409 del backend sin cerrar el modal', async () => {
    const user = userEvent.setup()
    const setStatus = vi.fn(async () => {
      throw new ApiError(409, 'no se puede modificar un ticket cerrado')
    })
    const api = createTicketsApiFake({
      getTicket: vi.fn(async () => buildTicket({ status: 'Resuelto' })),
      setStatus,
    })
    renderModal(api)

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    await user.selectOptions(
      within(dialog).getByLabelText('Cambiar estado'),
      'En progreso',
    )
    await user.click(
      within(dialog).getByRole('button', { name: 'Cambiar estado' }),
    )

    expect(
      await within(dialog).findByText(
        'no se puede modificar un ticket cerrado',
      ),
    ).toBeVisible()
    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('deshabilita las acciones de un ticket cerrado', async () => {
    renderModal(
      createTicketsApiFake({
        getTicket: vi.fn(async () => buildTicket({ status: 'Cerrado' })),
      }),
    )

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    expect(
      await within(dialog).findByText(
        'El ticket está cerrado; solo admite lectura.',
      ),
    ).toBeVisible()
    expect(
      within(dialog).getByText('Sin transiciones disponibles'),
    ).toBeVisible()
    expect(
      within(dialog).queryByLabelText('Nuevo comentario'),
    ).not.toBeInTheDocument()
  })

  it('añade un comentario recortado y conserva el error si falla', async () => {
    const user = userEvent.setup()
    const addComment = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(500, 'falló el seguimiento'))
      .mockResolvedValueOnce(buildComment())
    const api = createTicketsApiFake({ addComment })
    renderModal(api)

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    const input = within(dialog).getByLabelText('Nuevo comentario')
    await user.type(input, '  Revisando el caso  ')
    await user.click(
      within(dialog).getByRole('button', { name: 'Añadir comentario' }),
    )

    expect(await within(dialog).findByText('falló el seguimiento')).toBeVisible()
    expect(input).toHaveValue('  Revisando el caso  ')

    await user.click(
      within(dialog).getByRole('button', { name: 'Añadir comentario' }),
    )

    await waitFor(() =>
      expect(addComment).toHaveBeenLastCalledWith(
        TICKET_ID,
        'Revisando el caso',
      ),
    )
    expect(await within(dialog).findByText('Comentario añadido.')).toBeVisible()
    expect(input).toHaveValue('')
  })

  it('valida que el comentario no esté vacío', async () => {
    const user = userEvent.setup()
    const api = createTicketsApiFake()
    renderModal(api)

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    await user.click(
      within(dialog).getByRole('button', { name: 'Añadir comentario' }),
    )

    expect(
      await within(dialog).findByText('Escribe un comentario.'),
    ).toBeVisible()
    expect(api.addComment).not.toHaveBeenCalled()
  })

  it('el técnico puede cambiar estado pero no asignar', async () => {
    renderModal(createTicketsApiFake(), TECNICO)

    const dialog = await screen.findByRole('dialog', {
      name: 'Detalle del ticket',
    })
    expect(within(dialog).getByLabelText('Cambiar estado')).toBeVisible()
    expect(
      within(dialog).queryByLabelText('Asignar técnico'),
    ).not.toBeInTheDocument()
  })

  it('cierra con Escape y avisa al contenedor', async () => {
    const user = userEvent.setup()
    const { onClose } = renderModal()
    await screen.findByRole('dialog', { name: 'Detalle del ticket' })

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalled()
  })
})
