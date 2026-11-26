import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'

import MyTicketsPage from '@/pages/MyTicketsPage'
import TicketsPage from '@/pages/TicketsPage'
import {
  ADMIN,
  CLIENTE,
  SUPERVISOR,
  TECNICO,
  renderApp,
} from '../helpers/renderApp'
import {
  ASSIGNEE,
  buildSla,
  buildSummary,
  createTicketsApiFake,
} from '../helpers/ticketFixtures'
import type { AuthUser } from '@/types/domain'
import type { TicketSummary } from '@/types/ticket'

const OTHER = { id: 'u-other', name: 'Otro Técnico' }

const portal = buildSummary({
  id: 't-acpt0001',
  title: 'Acceso al portal',
  status: 'Abierto',
  priority: 'Alta',
  assignee: null,
  requester: { name: 'María Pérez' },
  sla: buildSla({ status: 'en_riesgo' }),
  created_at: '2026-11-10T08:00:00+00:00',
})

const licencia = buildSummary({
  id: 't-acpt0002',
  title: 'Licencia de software',
  status: 'Cerrado',
  priority: 'Baja',
  assignee: ASSIGNEE,
  requester: { name: 'María Gómez' },
  sla: buildSla({ status: 'cumplido' }),
  created_at: '2026-11-11T08:00:00+00:00',
})

const servidor = buildSummary({
  id: 't-acpt0003',
  title: 'Servidor caído',
  status: 'En progreso',
  priority: 'Crítica',
  assignee: OTHER,
  requester: { name: 'Otra Persona' },
  sla: buildSla({ status: 'incumplido' }),
  created_at: '2026-11-12T08:00:00+00:00',
})

const consulta = buildSummary({
  id: 't-acpt0004',
  title: 'Consulta general',
  status: 'Abierto',
  priority: 'Media',
  assignee: null,
  requester: null,
  sla: null,
  created_at: '2026-11-13T08:00:00+00:00',
})

const backup = buildSummary({
  id: 't-acpt0005',
  title: 'Backup pendiente',
  status: 'Abierto',
  priority: 'Alta',
  assignee: null,
  requester: { name: 'Luis López' },
  sla: buildSla({ status: 'en_tiempo' }),
  created_at: '2026-11-14T08:00:00+00:00',
})

const TICKETS = [portal, licencia, servidor, consulta, backup]
const TITLES = TICKETS.map((ticket) => ticket.title)

type ViewKey = 'all' | 'mine' | 'assigned'

interface ViewCase {
  name: string
  view: ViewKey
  user: AuthUser
  technician: boolean
}

const VIEWS: ViewCase[] = [
  {
    name: 'Todos los tickets · administrador',
    view: 'all',
    user: ADMIN,
    technician: true,
  },
  {
    name: 'Todos los tickets · técnico',
    view: 'all',
    user: TECNICO,
    technician: true,
  },
  {
    name: 'Todos los tickets · supervisor',
    view: 'all',
    user: SUPERVISOR,
    technician: false,
  },
  {
    name: 'Mis tickets · administrador',
    view: 'mine',
    user: ADMIN,
    technician: true,
  },
  {
    name: 'Mis tickets · técnico (asignados)',
    view: 'assigned',
    user: TECNICO,
    technician: true,
  },
  {
    name: 'Mis tickets · cliente',
    view: 'mine',
    user: CLIENTE,
    technician: false,
  },
]

function renderView(
  view: ViewKey,
  user: AuthUser,
  route = '/',
  tickets: readonly TicketSummary[] = TICKETS,
) {
  const api = createTicketsApiFake({
    listAll: vi.fn(async () => (view === 'all' ? [...tickets] : [])),
    listMine: vi.fn(async () => (view === 'mine' ? [...tickets] : [])),
    listAssigned: vi.fn(async () => (view === 'assigned' ? [...tickets] : [])),
  })
  const ui =
    view === 'all' ? <TicketsPage api={api} /> : <MyTicketsPage api={api} />

  return { api, ...renderApp(ui, { user, route }) }
}

function routeWith(params: Record<string, string>): string {
  return `/?${new URLSearchParams(params).toString()}`
}

interface CriterionCase {
  name: string
  params: Record<string, string>
  expected: string
}

const CRITERIA: CriterionCase[] = [
  {
    name: 'texto por título',
    params: { q: 'servidor' },
    expected: servidor.title,
  },
  {
    name: 'texto por ID parcial sin distinguir mayúsculas',
    params: { q: 'ACPT0002' },
    expected: licencia.title,
  },
  { name: 'estado', params: { status: 'Cerrado' }, expected: licencia.title },
  { name: 'prioridad', params: { priority: 'Baja' }, expected: licencia.title },
  {
    name: 'solicitante por nombre parcial',
    params: { requester: 'gómez' },
    expected: licencia.title,
  },
  {
    name: 'SLA concreto',
    params: { sla: 'en_riesgo' },
    expected: portal.title,
  },
  { name: 'sin SLA', params: { sla: 'none' }, expected: consulta.title },
]

const TECHNICIAN_CRITERION: CriterionCase = {
  name: 'técnico',
  params: { assignee: ASSIGNEE.id },
  expected: licencia.title,
}

function expectOnly(expected: string) {
  for (const title of TITLES) {
    if (title === expected) {
      expect(screen.getByText(title)).toBeVisible()
    } else {
      expect(screen.queryByText(title)).not.toBeInTheDocument()
    }
  }
  expect(screen.getByText('Mostrando 1–1 de 1')).toBeVisible()
}

function SearchProbe() {
  const location = useLocation()
  return <output data-testid="search">{location.search}</output>
}

describe.each(VIEWS)('aceptación HU-17 · $name', (viewCase) => {
  const criteria = viewCase.technician
    ? [...CRITERIA, TECHNICIAN_CRITERION]
    : CRITERIA

  it.each(criteria)(
    'aplica el criterio $name sobre la fuente autorizada',
    async ({ params, expected }) => {
      renderView(viewCase.view, viewCase.user, routeWith(params))

      expect(await screen.findByText(expected)).toBeVisible()
      expectOnly(expected)
    },
  )

  it('mantiene los estados transversales y no muestra datos demo', async () => {
    renderView(viewCase.view, viewCase.user)

    expect(await screen.findByText(portal.title)).toBeVisible()
    expect(screen.getByText('Mostrando 1–5 de 5')).toBeVisible()
    expect(document.body.textContent).not.toMatch(/demo/i)
  })
})

describe('aceptación HU-17 · combinaciones y URL compartida', () => {
  it('combina todos los criterios disponibles con AND', async () => {
    renderView(
      'all',
      ADMIN,
      routeWith({
        q: 'licencia',
        status: 'Cerrado',
        priority: 'Baja',
        requester: 'gómez',
        assignee: ASSIGNEE.id,
        sla: 'cumplido',
      }),
    )

    expect(await screen.findByText(licencia.title)).toBeVisible()
    expectOnly(licencia.title)
    expect(screen.getByLabelText('Buscar tickets')).toHaveValue('licencia')
    expect(screen.getByLabelText('Estado')).toHaveValue('Cerrado')
    expect(screen.getByLabelText('Prioridad')).toHaveValue('Baja')
    expect(screen.getByLabelText('Solicitante')).toHaveValue('gómez')
    expect(screen.getByLabelText('Técnico')).toHaveValue(ASSIGNEE.id)
    expect(screen.getByLabelText('Estado del SLA')).toHaveValue('cumplido')
  })

  it('no devuelve coincidencias si un solo criterio de la combinación falla', async () => {
    renderView(
      'all',
      ADMIN,
      routeWith({
        q: 'licencia',
        status: 'Abierto',
        priority: 'Baja',
        requester: 'gómez',
        assignee: ASSIGNEE.id,
        sla: 'cumplido',
      }),
    )

    expect(
      await screen.findByText('No encontramos tickets con esos filtros'),
    ).toBeVisible()
    for (const title of TITLES) {
      expect(screen.queryByText(title)).not.toBeInTheDocument()
    }
  })

  it('distingue los cuatro estados concretos de SLA y «Sin SLA»', async () => {
    const states: Array<[string, string]> = [
      ['en_tiempo', backup.title],
      ['en_riesgo', portal.title],
      ['cumplido', licencia.title],
      ['incumplido', servidor.title],
      ['none', consulta.title],
    ]

    for (const [sla, expected] of states) {
      const { unmount } = renderView(
        'all',
        ADMIN,
        routeWith({ sla }),
      )
      expect(await screen.findByText(expected)).toBeVisible()
      expectOnly(expected)
      unmount()
    }
  })

  it('serializa los criterios y una dirección recargada reproduce el resultado', async () => {
    const user = userEvent.setup()
    const api = createTicketsApiFake({
      listAll: vi.fn(async () => [...TICKETS]),
    })
    const first = renderApp(
      <>
        <TicketsPage api={api} />
        <SearchProbe />
      </>,
      { user: ADMIN, route: '/' },
    )
    await screen.findByText(portal.title)

    await user.selectOptions(screen.getByLabelText('Estado'), 'Cerrado')
    await user.selectOptions(screen.getByLabelText('Prioridad'), 'Baja')

    await waitFor(() =>
      expect(screen.getByTestId('search')).toHaveTextContent(
        'status=Cerrado',
      ),
    )
    const search = screen.getByTestId('search').textContent ?? ''
    expect(search).toContain('priority=Baja')
    expect(screen.getByText(licencia.title)).toBeVisible()
    expectOnly(licencia.title)
    first.unmount()

    renderView('all', ADMIN, `/${search}`)

    expect(await screen.findByText(licencia.title)).toBeVisible()
    expectOnly(licencia.title)
    expect(screen.getByLabelText('Estado')).toHaveValue('Cerrado')
    expect(screen.getByLabelText('Prioridad')).toHaveValue('Baja')
  })
})

describe('aceptación HU-17 · roles, permisos y criterios no disponibles', () => {
  it('el supervisor carga Todos los tickets de su empresa sin técnico, Mis tickets ni atención nueva', async () => {
    const { api } = renderView(
      'all',
      SUPERVISOR,
      routeWith({ assignee: ASSIGNEE.id }),
    )

    expect(await screen.findByText(portal.title)).toBeVisible()
    expect(screen.getByText(servidor.title)).toBeVisible()
    expect(screen.getByText('Mostrando 1–5 de 5')).toBeVisible()
    expect(api.listAll).toHaveBeenCalledTimes(1)
    expect(api.listMine).not.toHaveBeenCalled()
    expect(api.listAssigned).not.toHaveBeenCalled()
    expect(screen.queryByLabelText('Técnico')).not.toBeInTheDocument()
    expect(
      screen.queryByText('Tickets que requieren atención ahora'),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Mis tickets' })).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/demo/i)
  })

  it('el cliente solo usa Mis tickets y una URL con técnico no restringe su lista', async () => {
    const { api } = renderView(
      'mine',
      CLIENTE,
      routeWith({ assignee: ASSIGNEE.id }),
    )

    expect(await screen.findByText(portal.title)).toBeVisible()
    expect(screen.getByText(licencia.title)).toBeVisible()
    expect(screen.getByText('Mostrando 1–5 de 5')).toBeVisible()
    expect(api.listMine).toHaveBeenCalledTimes(1)
    expect(api.listAll).not.toHaveBeenCalled()
    expect(api.listAssigned).not.toHaveBeenCalled()
    expect(screen.queryByLabelText('Técnico')).not.toBeInTheDocument()
    expect(screen.getByText('Solicitudes que has creado.')).toBeVisible()
  })

  it.each([
    { label: 'Todos los tickets', view: 'all' as ViewKey, user: ADMIN },
    { label: 'Todos los tickets', view: 'all' as ViewKey, user: TECNICO },
    { label: 'Mis tickets', view: 'mine' as ViewKey, user: ADMIN },
    { label: 'Mis tickets', view: 'assigned' as ViewKey, user: TECNICO },
  ])(
    '$label permite el filtro de técnico a $user.role',
    async ({ view, user }) => {
      renderView(view, user)

      expect(await screen.findByText(portal.title)).toBeVisible()
      expect(screen.getByLabelText('Técnico')).toBeInTheDocument()
    },
  )
})

describe('aceptación HU-17 · carga y sesión expirada en ambas vistas', () => {
  it.each([
    { label: 'Todos los tickets', view: 'all' as ViewKey, user: ADMIN },
    { label: 'Mis tickets', view: 'mine' as ViewKey, user: CLIENTE },
  ])(
    '$label muestra la carga del listado',
    async ({ view, user }) => {
      const pending = vi.fn(
        () => new Promise<TicketSummary[]>(() => undefined),
      )
      const api = createTicketsApiFake({
        listAll: pending,
        listMine: pending,
      })
      const ui =
        view === 'all' ? <TicketsPage api={api} /> : <MyTicketsPage api={api} />
      renderApp(ui, { user })

      expect(
        await screen.findByRole('status', { name: 'Cargando tickets' }),
      ).toBeVisible()
    },
  )
})
