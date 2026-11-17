import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/httpClient'
import {
  type CompaniesApi,
  type CompanySummary,
  type UnassignedAccount,
} from '@/api/companies.api'
import CompaniesPage from '@/pages/CompaniesPage'
import { invitationDeliveryMessage } from '@/lib/invitations'

function buildCompany(overrides: Partial<CompanySummary> = {}): CompanySummary {
  return {
    id: 'c-1',
    name: 'Acme Solutions',
    email: 'contacto@acme.dev',
    phone: '+57 300 000 0000',
    contact_name: 'Ana Contacto',
    status: 'active',
    created_at: '2026-01-05T10:00:00+00:00',
    users_total: 3,
    tickets_total: 5,
    tickets_by_status: {
      Abierto: 2,
      'En progreso': 1,
      Resuelto: 1,
      Cerrado: 1,
    },
    has_administrator: true,
    administrator_invitation_pending: false,
    ...overrides,
  }
}

const UNASSIGNED: UnassignedAccount = {
  id: 'u-1',
  name: 'Sofía Sin Empresa',
  email: 'sofia@example.com',
  role: 'cliente',
  status: 'active',
}

function buildApi(overrides: Partial<CompaniesApi> = {}): CompaniesApi {
  return {
    list: vi.fn(async () => [] as CompanySummary[]),
    // El administrador de plataforma no tiene empresa propia (RF-142).
    getMine: vi.fn(async (): Promise<CompanySummary> => {
      throw new ApiError(404, 'company not found')
    }),
    updateMine: vi.fn(async () => buildCompany()),
    create: vi.fn(async () => ({ company: buildCompany() })),
    update: vi.fn(async () => buildCompany()),
    updateStatus: vi.fn(async () => buildCompany()),
    inviteAdministrator: vi.fn(async () => ({
      company: buildCompany(),
      email_status: 'sent' as const,
    })),
    resendAdministratorInvitation: vi.fn(async () => ({
      company: buildCompany(),
      email_status: 'sent' as const,
    })),
    listUnassigned: vi.fn(async () => [] as UnassignedAccount[]),
    associateAccount: vi.fn(async () => ({ company: buildCompany() })),
    ...overrides,
  }
}

function renderPage(api: CompaniesApi) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <CompaniesPage api={api} />
    </QueryClientProvider>,
  )
}

function ficha() {
  return screen.getByRole('region', { name: 'Ficha de la empresa' })
}

describe('sección de empresas', () => {
  it('muestra el catálogo y la ficha con sus agregados al administrador de plataforma', async () => {
    const api = buildApi({
      list: vi.fn(async () => [
        buildCompany(),
        buildCompany({ id: 'c-2', name: 'Globex', has_administrator: false }),
      ]),
    })

    renderPage(api)

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Ficha de la empresa' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ver ficha Acme Solutions' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ver ficha Globex' }),
    ).toBeInTheDocument()

    const detalle = within(ficha())
    expect(detalle.getByText('Acme Solutions')).toBeInTheDocument()
    expect(detalle.getByText('contacto@acme.dev')).toBeInTheDocument()
    expect(detalle.getByText('+57 300 000 0000')).toBeInTheDocument()
    expect(detalle.getByText('Ana Contacto')).toBeInTheDocument()
    expect(detalle.getByText('Activa')).toBeInTheDocument()
    expect(detalle.getByText('3')).toBeInTheDocument()
    expect(detalle.getByText('5')).toBeInTheDocument()
    expect(detalle.getByText('Abierto')).toBeInTheDocument()
    expect(detalle.getByText('En progreso')).toBeInTheDocument()
    expect(detalle.getByText('Resuelto')).toBeInTheDocument()
    expect(detalle.getByText('Cerrado')).toBeInTheDocument()
    expect(api.getMine).toHaveBeenCalledOnce()
  })

  it('cambia la ficha visible al elegir otra empresa del catálogo', async () => {
    const api = buildApi({
      list: vi.fn(async () => [
        buildCompany(),
        buildCompany({
          id: 'c-2',
          name: 'Globex',
          has_administrator: false,
          tickets_total: 0,
          tickets_by_status: {
            Abierto: 0,
            'En progreso': 0,
            Resuelto: 0,
            Cerrado: 0,
          },
        }),
      ]),
    })
    const user = userEvent.setup()

    renderPage(api)

    await user.click(
      await screen.findByRole('button', { name: 'Ver ficha Globex' }),
    )

    const detalle = within(ficha())
    expect(detalle.getByText('Globex')).toBeInTheDocument()
    expect(detalle.getByText('La empresa no tiene administrador.')).toBeInTheDocument()
    expect(
      within(ficha()).getByRole('button', { name: 'Invitar administrador' }),
    ).toBeInTheDocument()
  })

  it('reutiliza el estado vacío cuando no hay empresas', async () => {
    renderPage(buildApi())

    expect(await screen.findByText('Aún no hay empresas')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Crea la primera empresa para empezar a gestionar clientes.',
      ),
    ).toBeInTheDocument()
  })

  it('reutiliza el estado de error y permite reintentar', async () => {
    const list = vi
      .fn<CompaniesApi['list']>()
      .mockRejectedValueOnce(new ApiError(500, 'sin conexión'))
      .mockResolvedValueOnce([])
    const user = userEvent.setup()

    renderPage(buildApi({ list }))

    expect(
      await screen.findByText('No se pudo cargar la información de empresas'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('Aún no hay empresas')).toBeInTheDocument()
    expect(list).toHaveBeenCalledTimes(2)
  })

  it('crea una empresa con su administrador y avisa del resultado del correo', async () => {
    const create = vi.fn(async () => ({
      company: buildCompany(),
      email_status: 'failed' as const,
    }))
    const user = userEvent.setup()

    renderPage(buildApi({ create }))

    const form = within(
      await screen.findByRole('region', { name: 'Nueva empresa' }),
    )
    await user.type(form.getByLabelText('Nombre de la empresa'), 'Initech')
    await user.type(form.getByLabelText('Correo de contacto'), 'hola@initech.dev')
    await user.click(
      form.getByLabelText('Invitar a un administrador al crear la empresa'),
    )
    await user.type(
      form.getByLabelText('Nombre del administrador'),
      'Ada Admin',
    )
    await user.type(
      form.getByLabelText('Correo del administrador'),
      'ada@initech.dev',
    )
    await user.click(form.getByRole('button', { name: 'Crear empresa' }))

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith({
        name: 'Initech',
        email: 'hola@initech.dev',
        phone: null,
        contact_name: null,
        administrator: { name: 'Ada Admin', email: 'ada@initech.dev' },
      }),
    )
    expect(
      await screen.findByText(invitationDeliveryMessage('failed') as string),
    ).toBeInTheDocument()
  })

  it('muestra solo la ficha propia al administrador de empresa', async () => {
    const api = buildApi({ getMine: vi.fn(async () => buildCompany()) })

    renderPage(api)

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Ficha de la empresa' }),
    ).toBeInTheDocument()
    expect(within(ficha()).getByText('Acme Solutions')).toBeInTheDocument()

    expect(api.list).not.toHaveBeenCalled()
    expect(
      screen.queryByRole('region', { name: 'Nueva empresa' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Invitar administrador' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Reenviar invitación' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Desactivar empresa' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Asociar cuenta' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('region', { name: 'Editar datos' }),
    ).toBeInTheDocument()
  })

  it('actualiza la empresa propia sin enviar identificador', async () => {
    const updateMine = vi.fn(async () => buildCompany({ name: 'Renombrada' }))
    const user = userEvent.setup()

    renderPage(
      buildApi({
        getMine: vi.fn(async () => buildCompany()),
        updateMine,
      }),
    )

    const form = within(
      await screen.findByRole('region', { name: 'Editar datos' }),
    )
    const name = form.getByLabelText('Nombre de la empresa')
    await user.clear(name)
    await user.type(name, 'Renombrada')
    await user.click(form.getByRole('button', { name: 'Guardar cambios' }))

    await waitFor(() =>
      expect(updateMine).toHaveBeenCalledWith({ name: 'Renombrada' }),
    )
    expect(await screen.findByText('Cambios guardados.')).toBeInTheDocument()
  })

  it('ofrece invitar al administrador cuando la empresa no tiene ninguno', async () => {
    const inviteAdministrator = vi.fn(async () => ({
      company: buildCompany({ administrator_invitation_pending: true }),
      email_status: 'not-attempted' as const,
    }))
    const user = userEvent.setup()

    renderPage(
      buildApi({
        list: vi.fn(async () => [
          buildCompany({ has_administrator: false }),
        ]),
        inviteAdministrator,
      }),
    )

    await user.click(
      await screen.findByRole('button', { name: 'Invitar administrador' }),
    )
    await user.type(
      screen.getByLabelText('Nombre del administrador'),
      'Ada Admin',
    )
    await user.type(
      screen.getByLabelText('Correo del administrador'),
      'ada@acme.dev',
    )
    await user.click(screen.getByRole('button', { name: 'Enviar invitación' }))

    await waitFor(() =>
      expect(inviteAdministrator).toHaveBeenCalledWith('c-1', {
        name: 'Ada Admin',
        email: 'ada@acme.dev',
      }),
    )
    expect(
      await screen.findByText(
        invitationDeliveryMessage('not-attempted') as string,
      ),
    ).toBeInTheDocument()
  })

  it('ofrece reenviar la invitación pendiente sin cuerpo', async () => {
    const resendAdministratorInvitation = vi.fn(async () => ({
      company: buildCompany({ administrator_invitation_pending: true }),
      email_status: 'not-attempted' as const,
    }))
    const user = userEvent.setup()

    renderPage(
      buildApi({
        list: vi.fn(async () => [
          buildCompany({
            has_administrator: false,
            administrator_invitation_pending: true,
          }),
        ]),
        resendAdministratorInvitation,
      }),
    )

    await user.click(
      await screen.findByRole('button', { name: 'Reenviar invitación' }),
    )

    await waitFor(() =>
      expect(resendAdministratorInvitation).toHaveBeenCalledWith('c-1'),
    )
    expect(
      await screen.findByText(
        invitationDeliveryMessage('not-attempted') as string,
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Invitar administrador' }),
    ).not.toBeInTheDocument()
  })

  it('controla el estado de la empresa solo en el alcance de plataforma', async () => {
    const updateStatus = vi.fn(async () => buildCompany({ status: 'inactive' }))
    const user = userEvent.setup()

    renderPage(buildApi({ list: vi.fn(async () => [buildCompany()]), updateStatus }))

    await user.click(
      await screen.findByRole('button', { name: 'Desactivar empresa' }),
    )

    await waitFor(() =>
      expect(updateStatus).toHaveBeenCalledWith('c-1', 'inactive'),
    )
    expect(await screen.findByText('Empresa desactivada.')).toBeInTheDocument()
  })

  it('asocia una cuenta sin empresa elegida del listado', async () => {
    const associateAccount = vi.fn(async () => ({ company: buildCompany() }))
    const user = userEvent.setup()

    renderPage(
      buildApi({
        list: vi.fn(async () => [buildCompany({ users_total: 0 })]),
        listUnassigned: vi.fn(async () => [UNASSIGNED]),
        associateAccount,
      }),
    )

    const select = await screen.findByLabelText('Cuenta')
    await user.selectOptions(select, 'u-1')
    await user.click(screen.getByRole('button', { name: 'Asociar cuenta' }))

    await waitFor(() =>
      expect(associateAccount).toHaveBeenCalledWith('c-1', 'u-1'),
    )
    expect(
      await screen.findByText('Cuenta asociada a la empresa.'),
    ).toBeInTheDocument()
  })

  it('no renderiza tokens ni enlaces de invitación en el DOM', async () => {
    const user = userEvent.setup()

    renderPage(
      buildApi({
        list: vi.fn(async () => [
          buildCompany({
            has_administrator: false,
            administrator_invitation_pending: true,
          }),
        ]),
      }),
    )

    await user.click(
      await screen.findByRole('button', { name: 'Reenviar invitación' }),
    )
    await screen.findByText('Invitación reenviada.')

    expect(document.body.textContent?.toLowerCase()).not.toContain('token')
    expect(document.querySelector('a')).toBeNull()
  })
})
