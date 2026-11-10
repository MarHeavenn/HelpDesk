import {
  Bell,
  Building2,
  Gauge,
  LayoutDashboard,
  LifeBuoy,
  ListChecks,
  PlusCircle,
  Ticket,
  UserRound,
  Users,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { Link, NavLink } from 'react-router-dom'

import { firstAllowedRoute, navItems, type NavIcon, type NavItem } from '@/lib/permissions'
import { strings } from '@/lib/strings'
import type { Rol } from '@/types/domain'

const ICONS: Record<NavIcon, LucideIcon> = {
  dashboard: LayoutDashboard,
  tickets: Ticket,
  'my-tickets': ListChecks,
  'create-ticket': PlusCircle,
  technicians: Wrench,
  sla: Gauge,
  users: Users,
  companies: Building2,
  notifications: Bell,
  account: UserRound,
}

function SidebarLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const Icon = ICONS[item.icon]

  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      onClick={onNavigate}
      className={({ isActive }) =>
        [
          'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition',
          isActive
            ? 'bg-primary-soft font-semibold text-primary'
            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          {isActive ? (
            <span
              aria-hidden="true"
              className="absolute inset-y-1.5 left-0 w-1 rounded-full bg-primary"
            />
          ) : null}
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{item.label}</span>
        </>
      )}
    </NavLink>
  )
}

/**
 * Contenido compartido de la barra lateral: lo usan la versión fija de
 * escritorio y el panel deslizante móvil (RF-70, RF-71, RF-74).
 */
export function SidebarContent({
  role,
  onNavigate,
}: {
  role: Rol
  onNavigate?: () => void
}) {
  const items = navItems(role)
  const mainItems = items.filter((item) => item.to !== '/cuenta/perfil')
  const bottomItems = items.filter((item) => item.to === '/cuenta/perfil')

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex h-16 items-center border-b border-slate-200 px-5">
        <Link
          to={firstAllowedRoute(role)}
          onClick={onNavigate}
          className="flex items-center gap-2 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-white">
            <LifeBuoy className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="text-lg font-semibold tracking-tight text-slate-900">
            {strings.app.name}
          </span>
        </Link>
      </div>

      <div className="px-4 py-4">
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <Building2 className="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">
              {strings.shell.workspace}
            </p>
            <p className="truncate text-xs text-slate-500">
              {strings.shell.workspacePlan}
            </p>
          </div>
        </div>
      </div>

      <nav
        aria-label="Navegación principal"
        className="flex-1 space-y-1 overflow-y-auto px-3 py-2"
      >
        {mainItems.map((item) => (
          <SidebarLink key={item.to} item={item} onNavigate={onNavigate} />
        ))}

        {bottomItems.length > 0 ? (
          <>
            <div className="my-3 border-t border-slate-200" />
            {bottomItems.map((item) => (
              <SidebarLink key={item.to} item={item} onNavigate={onNavigate} />
            ))}
          </>
        ) : null}
      </nav>

      <p className="border-t border-slate-200 px-5 py-4 text-xs text-slate-500">
        {strings.app.name} {strings.app.version} · {strings.app.prototype}
      </p>
    </div>
  )
}

/** Barra lateral fija del armazón en anchos de escritorio (RF-70, RF-74). */
export default function Sidebar({ role }: { role: Rol }) {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-slate-200 lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
      <SidebarContent role={role} />
    </aside>
  )
}
