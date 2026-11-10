import { Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'

import { useAuth } from '@/context/AuthContext'
import AppShell from '@/layout/AppShell'
import { firstAllowedRoute } from '@/lib/permissions'
import { strings } from '@/lib/strings'
import DashboardPage from '@/pages/DashboardPage'
import LoginPage from '@/pages/LoginPage'
import NotFoundPage from '@/pages/NotFoundPage'
import PlaceholderPage from '@/pages/PlaceholderPage'
import ProfilePage from '@/pages/ProfilePage'
import type { Rol } from '@/types/domain'

const ADMIN_ROLES: readonly Rol[] = ['administrador']
const STAFF_ROLES: readonly Rol[] = ['administrador', 'tecnico']

function SessionLoading() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <p role="status" className="text-sm text-slate-600">
        {strings.auth.checkingSession}
      </p>
    </main>
  )
}

function SessionError({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm space-y-3 rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <p role="alert" className="text-sm text-red-700">
          {strings.auth.sessionError}
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
        >
          {strings.common.retry}
        </button>
        <Link
          to="/login"
          className="block text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          {strings.auth.title}
        </Link>
      </div>
    </main>
  )
}

/** Exige sesión; conserva la sesión local ante errores de red (RF-69, RF-80). */
export function RequireAuth() {
  const { user, status, refresh } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <SessionLoading />
  if (status === 'error' && !user) {
    return <SessionError onRetry={() => void refresh()} />
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

/** Exige un rol; si no lo tiene, vuelve a su primera ruta con aviso (RF-71). */
export function RequireRole({ allow }: { allow: readonly Rol[] }) {
  const { user } = useAuth()

  if (!user) return <Navigate to="/login" replace />
  if (!allow.includes(user.role)) {
    return (
      <Navigate
        to={firstAllowedRoute(user.role)}
        replace
        state={{ denied: true }}
      />
    )
  }
  return <Outlet />
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route element={<RequireRole allow={STAFF_ROLES} />}>
            <Route path="/" element={<DashboardPage />} />
            <Route
              path="/tickets"
              element={
                <PlaceholderPage title={strings.routes.titles['/tickets']} />
              }
            />
          </Route>

          <Route
            path="/mis-tickets"
            element={
              <PlaceholderPage title={strings.routes.titles['/mis-tickets']} />
            }
          />
          <Route
            path="/tickets/nuevo"
            element={
              <PlaceholderPage title={strings.routes.titles['/tickets/nuevo']} />
            }
          />

          <Route element={<RequireRole allow={ADMIN_ROLES} />}>
            <Route
              path="/tecnicos"
              element={
                <PlaceholderPage title={strings.routes.titles['/tecnicos']} />
              }
            />
            <Route
              path="/sla"
              element={<PlaceholderPage title={strings.routes.titles['/sla']} />}
            />
            <Route
              path="/usuarios"
              element={
                <PlaceholderPage title={strings.routes.titles['/usuarios']} />
              }
            />
            <Route
              path="/empresas"
              element={
                <PlaceholderPage title={strings.routes.titles['/empresas']} />
              }
            />
          </Route>

          <Route
            path="/notificaciones"
            element={
              <PlaceholderPage
                title={strings.routes.titles['/notificaciones']}
              />
            }
          />
          <Route path="/cuenta" element={<Navigate to="/cuenta/perfil" replace />} />
          <Route path="/cuenta/perfil" element={<ProfilePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
