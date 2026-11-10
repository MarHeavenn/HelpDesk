/**
 * Cobertura RF-74 (drawer móvil accesible) y RF-75 (foco, etiquetas y
 * `aria-expanded`/`aria-controls`).
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { AuthProvider } from '@/context/AuthContext'
import AppShell from '@/layout/AppShell'
import AppRoutes from '@/routes'
import { ADMIN, createAuthApi, renderApp } from '../helpers/renderApp'

type MediaListener = (event: MediaQueryListEvent) => void

function stubMatchMedia(matches = false) {
  const listeners: MediaListener[] = []
  const media = {
    matches,
    media: '(min-width: 1024px)',
    onchange: null,
    addEventListener: (_: string, listener: MediaListener) => {
      listeners.push(listener)
    },
    removeEventListener: (_: string, listener: MediaListener) => {
      const index = listeners.indexOf(listener)
      if (index >= 0) listeners.splice(index, 1)
    },
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn(() => media),
  })

  return {
    listeners,
    crossThreshold() {
      for (const listener of listeners) {
        listener({ matches: true } as MediaQueryListEvent)
      }
    },
  }
}

function renderShell() {
  return renderApp(
    <AppShell>
      <p>contenido de la vista</p>
    </AppShell>,
    { user: ADMIN, route: '/' },
  )
}

function renderRoutes(route: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider api={createAuthApi(ADMIN)}>
        <MemoryRouter initialEntries={[route]}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('MobileSidebar', () => {
  it('abre el panel con el estado accesible y enfoca su cierre', async () => {
    renderShell()
    await screen.findByText('Ana Admin')
    const user = userEvent.setup()

    const trigger = screen.getByRole('button', { name: 'Abrir menú' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveAttribute('aria-controls')

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const dialog = screen.getByRole('dialog', { name: 'Menú de navegación' })
    expect(dialog).toBeInTheDocument()
    expect(
      within(dialog).getByRole('button', { name: 'Cerrar menú' }),
    ).toHaveFocus()
  })

  it('cierra con Escape y devuelve el foco al botón que lo abrió', async () => {
    renderShell()
    await screen.findByText('Ana Admin')
    const user = userEvent.setup()

    const trigger = screen.getByRole('button', { name: 'Abrir menú' })
    await user.click(trigger)
    expect(screen.getByRole('dialog', { name: 'Menú de navegación' })).toBeInTheDocument()

    await user.keyboard('{Escape}')

    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Menú de navegación' }),
      ).not.toBeInTheDocument(),
    )
    expect(trigger).toHaveFocus()
  })

  it('cierra al pulsar la capa oscura', async () => {
    renderShell()
    await screen.findByText('Ana Admin')
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Abrir menú' }))
    await user.click(screen.getByTestId('mobile-sidebar-overlay'))

    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Menú de navegación' }),
      ).not.toBeInTheDocument(),
    )
  })

  it('atrapa el foco dentro del panel mientras está abierto', async () => {
    renderShell()
    await screen.findByText('Ana Admin')
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Abrir menú' }))
    const dialog = screen.getByRole('dialog', { name: 'Menú de navegación' })
    const close = within(dialog).getByRole('button', { name: 'Cerrar menú' })

    expect(close).toHaveFocus()

    await user.tab({ shift: true })
    expect(within(dialog).getByRole('link', { name: 'Cuenta' })).toHaveFocus()

    await user.tab()
    expect(close).toHaveFocus()
  })

  it('se cierra al cambiar de ruta', async () => {
    renderRoutes('/mis-tickets')
    await screen.findByRole('heading', { level: 1, name: 'Mis tickets' })
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Abrir menú' }))
    const dialog = screen.getByRole('dialog', { name: 'Menú de navegación' })
    await user.click(within(dialog).getByRole('link', { name: 'Todos los tickets' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Todos los tickets' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('dialog', { name: 'Menú de navegación' }),
    ).not.toBeInTheDocument()
  })

  it('descarta el estado móvil al cruzar el umbral de escritorio', async () => {
    const media = stubMatchMedia(false)
    renderShell()
    await screen.findByText('Ana Admin')
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Abrir menú' }))
    expect(screen.getByRole('dialog', { name: 'Menú de navegación' })).toBeInTheDocument()

    media.crossThreshold()

    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Menú de navegación' }),
      ).not.toBeInTheDocument(),
    )
  })
})
