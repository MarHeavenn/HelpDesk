import { afterEach, describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import AppShell from '@/layout/AppShell'
import PageHeader from '@/components/ui/PageHeader'
import { ADMIN, CLIENTE, TECNICO, createAuthApi, renderApp } from '../helpers/renderApp'
import type { AuthUser } from '@/types/domain'

function renderShell(user: AuthUser = ADMIN, route = '/') {
  return renderApp(
    <AppShell>
      <PageHeader
        title="Dashboard"
        subtitle="Resumen operativo"
        actions={<button type="button">Nuevo ticket</button>}
      />
      <p>contenido de la vista</p>
    </AppShell>,
    { user, route },
  )
}

afterEach(() => {
  localStorage.clear()
})

describe('AppShell', () => {
  it('muestra marca, espacio de trabajo, pie y encabezado de página', async () => {
    renderShell()

    expect(await screen.findByText('Ana Admin')).toBeInTheDocument()
    expect(screen.getAllByText('HelpDesk').length).toBeGreaterThan(0)
    expect(screen.getByText('Acme Solutions')).toBeInTheDocument()
    expect(screen.getByText('Plan Business')).toBeInTheDocument()
    expect(screen.getByText('HelpDesk v1.1 · Prototipo')).toBeInTheDocument()

    expect(screen.getByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByText('Resumen operativo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Nuevo ticket' })).toBeInTheDocument()
    expect(screen.getByText('contenido de la vista')).toBeInTheDocument()

    expect(screen.getByRole('searchbox', { name: 'Buscar' })).toBeInTheDocument()
    const banner = within(screen.getByRole('banner'))
    expect(banner.getByRole('link', { name: 'Notificaciones' })).toBeInTheDocument()
    expect(banner.getByRole('button', { name: 'Ayuda' })).toBeInTheDocument()
  })

  it('muestra al administrador toda la navegación', async () => {
    renderShell(ADMIN)

    await screen.findByText('Ana Admin')
    const nav = within(
      screen.getByRole('navigation', { name: 'Navegación principal' }),
    )
    for (const label of [
      'Dashboard',
      'Todos los tickets',
      'Mis tickets',
      'Crear ticket',
      'Técnicos',
      'SLA',
      'Usuarios',
      'Empresas',
      'Notificaciones',
      'Cuenta',
    ]) {
      expect(nav.getByRole('link', { name: label })).toBeInTheDocument()
    }
  })

  it('oculta al técnico las secciones de administración', async () => {
    renderShell(TECNICO)

    await screen.findByText('Tomás Técnico')
    const nav = within(
      screen.getByRole('navigation', { name: 'Navegación principal' }),
    )
    expect(nav.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(nav.getByRole('link', { name: 'Mis tickets' })).toBeInTheDocument()
    for (const label of ['Técnicos', 'SLA', 'Usuarios', 'Empresas']) {
      expect(nav.queryByRole('link', { name: label })).not.toBeInTheDocument()
    }
  })

  it('limita al cliente a sus tickets, creación, notificaciones y cuenta', async () => {
    renderShell(CLIENTE, '/mis-tickets')

    await screen.findByText('Carla Cliente')
    const nav = within(
      screen.getByRole('navigation', { name: 'Navegación principal' }),
    )
    for (const label of ['Mis tickets', 'Crear ticket', 'Notificaciones', 'Cuenta']) {
      expect(nav.getByRole('link', { name: label })).toBeInTheDocument()
    }
    for (const label of ['Dashboard', 'Todos los tickets', 'Técnicos', 'SLA']) {
      expect(nav.queryByRole('link', { name: label })).not.toBeInTheDocument()
    }
  })

  it('marca el ítem activo con aria-current="page"', async () => {
    renderShell(ADMIN, '/mis-tickets')

    await screen.findByText('Ana Admin')
    const nav = within(
      screen.getByRole('navigation', { name: 'Navegación principal' }),
    )
    expect(nav.getByRole('link', { name: 'Mis tickets' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(nav.getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('enfoca el buscador con Ctrl+K', async () => {
    renderShell()
    await screen.findByText('Ana Admin')
    const user = userEvent.setup()

    await user.keyboard('{Control>}k{/Control}')

    expect(screen.getByRole('searchbox', { name: 'Buscar' })).toHaveFocus()
  })

  it('abre el menú de usuario y lo cierra con Escape', async () => {
    renderShell()
    await screen.findByText('Ana Admin')
    const user = userEvent.setup()

    const trigger = screen.getByRole('button', { name: /Ana Admin/ })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(
      screen.getByRole('menu', { name: 'Menú de usuario' }),
    ).toHaveTextContent('admin@helpdesk.dev')
    expect(
      screen.getByRole('menu', { name: 'Menú de usuario' }),
    ).toHaveTextContent('Administrador')
    expect(screen.getByRole('menuitem', { name: 'Mi perfil' })).toBeInTheDocument()
    expect(
      screen.getByRole('menuitem', { name: 'Cerrar sesión' }),
    ).toBeInTheDocument()

    await user.keyboard('{Escape}')

    await waitFor(() =>
      expect(
        screen.queryByRole('menuitem', { name: 'Mi perfil' }),
      ).not.toBeInTheDocument(),
    )
  })

  it('cierra sesión desde el menú y vuelve a /login', async () => {
    const api = createAuthApi(ADMIN)
    renderApp(
      <AppShell>
        <p>contenido</p>
      </AppShell>,
      { api },
    )
    await screen.findByText('Ana Admin')
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /Ana Admin/ }))
    await user.click(screen.getByRole('menuitem', { name: 'Cerrar sesión' }))

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
    expect(api.logout).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('helpdesk.user')).toBeNull()
  })
})
