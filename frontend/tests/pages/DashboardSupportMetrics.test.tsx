import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/httpClient'
import { supportMetricsApi, type SupportMetricsApi } from '@/api/supportMetrics.api'
import { useAuth } from '@/context/AuthContext'
import DashboardPage from '@/pages/DashboardPage'
import type { AuthUser } from '@/types/domain'
import type { SupportMetrics } from '@/types/supportMetrics'
import { buildTicketDashboard, createDashboardApi } from '../helpers/dashboardFixtures'
import { createNotificationsApi } from '../helpers/notificationFixtures'
import { ADMIN, CLIENTE, SUPERVISOR, TECNICO, createAuthApi, renderApp } from '../helpers/renderApp'
import { buildSupportMetrics } from '../helpers/supportMetricsFixtures'

const title = 'Métricas de gestión de soporte'
const SECOND_ADMIN = { ...ADMIN, id: 'admin-other', name: 'Otra administradora' }

afterEach(() => {
  vi.unstubAllGlobals()
})

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function SessionControls() {
  const { status, user, login, logout, refresh } = useAuth()
  return (
    <>
      <p data-testid="session">{status}:{user?.id ?? 'none'}</p>
      <button onClick={() => void login('other@example.com', 'test')}>Cambiar actor</button>
      <button onClick={() => void logout()}>Salir</button>
      <button onClick={() => void refresh()}>Validar sesión</button>
    </>
  )
}

function setup({
  user = ADMIN,
  auth = createAuthApi(user, { login: vi.fn(async () => SECOND_ADMIN) }),
  api = createDashboardApi(),
  metrics = { getMetrics: vi.fn(async () => buildSupportMetrics()) },
}: {
  user?: AuthUser
  auth?: ReturnType<typeof createAuthApi>
  api?: ReturnType<typeof createDashboardApi>
  metrics?: SupportMetricsApi
} = {}) {
  const notifications = createNotificationsApi({
    list: async () => [], unreadCount: async () => ({ count: 0 }),
  })
  renderApp(
    <>
      <SessionControls />
      <DashboardPage api={api} notificationsApi={notifications} supportMetricsApi={metrics} />
    </>,
    { user, api: auth },
  )
  return { api, metrics, auth, ui: userEvent.setup() }
}

async function loadedPanel() {
  const panel = await screen.findByRole('region', { name: title })
  await within(panel).findByRole('article', { name: 'Tiempo promedio de resolución' })
  return panel
}

describe('DashboardPage — integración HU-18', () => {
  it('monta cinco indicadores para administrador sin sustituir HU-11/HU-12', async () => {
    const { metrics, api } = setup()
    const panel = await loadedPanel()
    expect(within(panel).getAllByRole('article')).toHaveLength(5)
    expect(within(panel).getByRole('article', { name: 'Resueltos' })).toHaveTextContent('3')
    expect(within(panel).getByText('120 minutos')).toBeInTheDocument()
    expect(within(panel).getByText('50 %')).toBeInTheDocument()
    expect(metrics.getMetrics).toHaveBeenCalledTimes(1)
    expect(metrics.getMetrics).toHaveBeenCalledWith(expect.any(AbortSignal))
    expect(await screen.findByRole('region', { name: 'Cumplimiento de SLA' })).toHaveTextContent('66.67%')
    expect(screen.getByRole('table', { name: 'Tickets recientes' })).toBeInTheDocument()
    expect(api.getTickets).toHaveBeenCalledTimes(1)
  })

  it.each([SUPERVISOR, TECNICO, CLIENTE])('no monta ni consulta para $role y conserva paneles previos', async (user) => {
    const { metrics } = setup({ user })
    await screen.findByRole('table', { name: 'Tickets recientes' })
    expect(screen.getByTestId('session')).toHaveTextContent(`authenticated:${user.id}`)
    expect(screen.getByRole('region', { name: 'Cumplimiento de SLA' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
    expect(metrics.getMetrics).not.toHaveBeenCalled()
    if (user.role === 'tecnico') {
      expect(screen.getByRole('region', { name: 'Alertas de SLA' })).toBeInTheDocument()
    }
  })

  it('no confía en el administrador almacenado mientras se valida la sesión', async () => {
    localStorage.setItem('helpdesk.user', JSON.stringify(ADMIN))
    const me = deferred<AuthUser>()
    const { metrics } = setup({ auth: createAuthApi(ADMIN, { me: () => me.promise }) })
    await screen.findByRole('table', { name: 'Tickets recientes' })
    expect(screen.getByTestId('session')).toHaveTextContent(`loading:${ADMIN.id}`)
    expect(metrics.getMetrics).not.toHaveBeenCalled()
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
    await act(async () => me.resolve(ADMIN))
    await loadedPanel()
    expect(metrics.getMetrics).toHaveBeenCalledTimes(1)
  })

  it.each([401, 500])('no consulta si la validación falla con %i aunque haya administrador almacenado', async (status) => {
    localStorage.setItem('helpdesk.user', JSON.stringify(ADMIN))
    const { metrics } = setup({
      auth: createAuthApi(ADMIN, { me: vi.fn().mockRejectedValue(new ApiError(status, 'failure')) }),
    })
    await waitFor(() => expect(screen.getByTestId('session')).toHaveTextContent(status === 401 ? 'anonymous:none' : 'error:u-admin'))
    expect(metrics.getMetrics).not.toHaveBeenCalled()
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
  })

  it('presenta HU-18 también cuando HU-11 está vacío', async () => {
    setup({ api: createDashboardApi({
      getTickets: vi.fn(async () => buildTicketDashboard({ total_tickets: 0, recent_tickets: [] })),
    }) })
    expect(await screen.findByText('Aún no hay tickets')).toBeInTheDocument()
    expect(await loadedPanel()).toHaveTextContent('120 minutos')
  })

  it('cambiar periodos de HU-12 no consulta ni altera la muestra histórica HU-18', async () => {
    const { metrics, api, ui } = setup()
    const panel = await loadedPanel()
    const before = panel.textContent
    const sla = await screen.findByRole('region', { name: 'Cumplimiento de SLA' })
    for (const days of [7, 90, 30]) {
      await ui.click(within(sla).getByRole('button', { name: `${days} días` }))
      await waitFor(() => expect(api.getSla).toHaveBeenLastCalledWith(days))
      expect(panel.textContent).toBe(before)
    }
    expect(metrics.getMetrics).toHaveBeenCalledTimes(1)
    expect(metrics.getMetrics).toHaveBeenCalledWith(expect.any(AbortSignal))
  })

  it('aplica cierre de sesión existente ante 401 de la API inyectada', async () => {
    const { auth, metrics } = setup({
      metrics: { getMetrics: vi.fn().mockRejectedValue(new ApiError(401, 'expired')) },
    })
    await waitFor(() => expect(auth.logout).toHaveBeenCalledTimes(1))
    expect(screen.getByTestId('session')).toHaveTextContent('anonymous:none')
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
    expect(metrics.getMetrics).toHaveBeenCalledTimes(1)
  })

  it('el cliente HTTP real retira la sesión ante un 401 vigente', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(
      JSON.stringify({ detail: 'not authenticated' }), { status: 401 },
    ))
    vi.stubGlobal('fetch', fetchMock)
    setup({ metrics: supportMetricsApi })
    await waitFor(() => expect(screen.getByTestId('session')).toHaveTextContent('anonymous:none'))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/dashboard/support-metrics')
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
  })

  it.each(['detail', 'abort'])('un 401 antiguo con cuerpo pendiente (%s) no afecta al nuevo actor usando HTTP real', async (result) => {
    // Fetch ya recibió las cabeceras 401, pero el cuerpo aún no se ha leído.
    // Al abortar entre ambos pasos, json() puede rechazar con AbortError.
    const body = deferred<unknown>()
    const oldResponse = new Response(null, { status: 401 })
    const readBody = vi.spyOn(oldResponse, 'json').mockImplementation(() => body.promise)
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(oldResponse)
      .mockImplementation(async () => new Response(JSON.stringify(buildSupportMetrics()), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }))
    vi.stubGlobal('fetch', fetchMock)
    const { ui } = setup({ metrics: supportMetricsApi })
    await waitFor(() => expect(readBody).toHaveBeenCalledTimes(1))
    const signal = fetchMock.mock.calls[0][1]?.signal
    expect(signal).toBeInstanceOf(AbortSignal)
    await ui.click(screen.getByRole('button', { name: 'Cambiar actor' }))
    const panel = await loadedPanel()
    expect(signal?.aborted).toBe(true)
    expect(screen.getByTestId('session')).toHaveTextContent(`authenticated:${SECOND_ADMIN.id}`)
    expect(panel).toHaveTextContent('120 minutos')

    await act(async () => {
      if (result === 'abort') body.reject(new DOMException('Aborted', 'AbortError'))
      else body.resolve({ detail: 'old session expired' })
    })

    expect(screen.getByTestId('session')).toHaveTextContent(`authenticated:${SECOND_ADMIN.id}`)
    expect(panel).toBeInTheDocument()
    expect(panel).toHaveTextContent('120 minutos')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('404 sin empresa visible no cierra sesión ni ofrece reintento/elevación ni métricas', async () => {
    const { auth, metrics } = setup({
      metrics: { getMetrics: vi.fn().mockRejectedValue(new ApiError(404, 'not found')) },
    })
    const panel = await screen.findByRole('region', { name: title })
    expect(await within(panel).findByRole('alert')).toHaveTextContent('no están disponibles')
    expect(within(panel).queryByRole('article')).not.toBeInTheDocument()
    expect(within(panel).queryByRole('button')).not.toBeInTheDocument()
    expect(auth.logout).not.toHaveBeenCalled()
    expect(metrics.getMetrics).toHaveBeenCalledTimes(1)
  })

  it('retira datos al salir y vuelve a consultar incluso si entra el mismo actor', async () => {
    const pending = deferred<SupportMetrics>()
    const metrics = { getMetrics: vi.fn()
      .mockResolvedValueOnce(buildSupportMetrics({ average_resolution_minutes: 987 }))
      .mockReturnValueOnce(pending.promise) }
    const { ui } = setup({ metrics, auth: createAuthApi(ADMIN) })
    expect(await loadedPanel()).toHaveTextContent('987 minutos')
    const signal = metrics.getMetrics.mock.calls[0][0] as AbortSignal
    await ui.click(screen.getByRole('button', { name: 'Salir' }))
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
    expect(signal.aborted).toBe(true)
    await ui.click(screen.getByRole('button', { name: 'Cambiar actor' }))
    await waitFor(() => expect(metrics.getMetrics).toHaveBeenCalledTimes(2))
    expect(screen.queryByText('987 minutos')).not.toBeInTheDocument()
    await act(async () => pending.resolve(buildSupportMetrics()))
    expect(await loadedPanel()).toHaveTextContent('120 minutos')
  })

  it('remonta sin mostrar datos anteriores al cambiar directamente de administrador', async () => {
    const next = deferred<SupportMetrics>()
    const metrics = { getMetrics: vi.fn()
      .mockResolvedValueOnce(buildSupportMetrics({ average_resolution_minutes: 987 }))
      .mockReturnValueOnce(next.promise) }
    const { ui } = setup({ metrics })
    const oldPanel = await loadedPanel()
    expect(oldPanel).toHaveTextContent('987 minutos')
    await ui.click(screen.getByRole('button', { name: 'Cambiar actor' }))
    expect(screen.getByTestId('session')).toHaveTextContent(`authenticated:${SECOND_ADMIN.id}`)
    expect(oldPanel).not.toBeInTheDocument()
    expect(screen.queryByText('987 minutos')).not.toBeInTheDocument()
    await act(async () => next.resolve(buildSupportMetrics()))
    expect(await loadedPanel()).toHaveTextContent('120 minutos')
    expect(metrics.getMetrics).toHaveBeenCalledTimes(2)
  })

  it.each(['success', '401', '404', 'network'])('descarta respuesta antigua %s tras cambiar de actor', async (result) => {
    const old = deferred<SupportMetrics>()
    const metrics = { getMetrics: vi.fn()
      .mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(buildSupportMetrics()) }
    const { ui, auth } = setup({ metrics })
    await waitFor(() => expect(metrics.getMetrics).toHaveBeenCalledTimes(1))
    const signal = metrics.getMetrics.mock.calls[0][0] as AbortSignal
    await ui.click(screen.getByRole('button', { name: 'Cambiar actor' }))
    expect(signal.aborted).toBe(true)
    const panel = await loadedPanel()
    const before = panel.textContent
    await act(async () => {
      if (result === 'success') old.resolve(buildSupportMetrics({ average_resolution_minutes: 987 }))
      else old.reject(result === 'network' ? new TypeError('network') : new ApiError(Number(result), 'old'))
    })
    expect(panel.textContent).toBe(before)
    expect(auth.logout).not.toHaveBeenCalled()
    expect(screen.getByTestId('session')).toHaveTextContent(`authenticated:${SECOND_ADMIN.id}`)
  })

  it('retira datos durante revalidación y no consulta si el rol validado ya no es administrador', async () => {
    const next = deferred<AuthUser>()
    const auth = createAuthApi(ADMIN, { me: vi.fn().mockResolvedValueOnce(ADMIN).mockReturnValueOnce(next.promise) })
    const { metrics, ui } = setup({ auth })
    await loadedPanel()
    await ui.click(screen.getByRole('button', { name: 'Validar sesión' }))
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
    await act(async () => next.resolve({ ...ADMIN, role: 'supervisor' }))
    expect(screen.getByTestId('session')).toHaveTextContent('authenticated:u-admin')
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
    expect(metrics.getMetrics).toHaveBeenCalledTimes(1)
  })

  it('descarta consulta pendiente al salir, incluso si luego responde con datos', async () => {
    const pending = deferred<SupportMetrics>()
    const metrics = { getMetrics: vi.fn<SupportMetricsApi['getMetrics']>(() => pending.promise) }
    const { ui } = setup({ metrics })
    await waitFor(() => expect(metrics.getMetrics).toHaveBeenCalledTimes(1))
    const signal = metrics.getMetrics.mock.calls[0][0] as AbortSignal
    await ui.click(screen.getByRole('button', { name: 'Salir' }))
    await act(async () => pending.resolve(buildSupportMetrics({ average_resolution_minutes: 987 })))
    expect(signal.aborted).toBe(true)
    expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument()
    expect(screen.queryByText('987 minutos')).not.toBeInTheDocument()
  })
})
