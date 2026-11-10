import { useNavigate } from 'react-router-dom'

import PageHeader from '@/components/ui/PageHeader'
import { useAuth } from '@/context/AuthContext'
import { strings } from '@/lib/strings'

/**
 * Datos reales de la sesión y cierre de sesión desde el perfil (RF-76).
 * La edición de datos de cuenta pertenece a una historia posterior.
 */
export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  async function handleLogout() {
    try {
      await logout()
    } finally {
      navigate('/login', { replace: true })
    }
  }

  return (
    <>
      <PageHeader
        title={strings.routes.titles['/cuenta/perfil']}
        subtitle={strings.profile.subtitle}
      />

      <section
        aria-label={strings.profile.sessionCard}
        className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <dl className="grid gap-5 sm:grid-cols-3">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {strings.profile.name}
            </dt>
            <dd className="mt-1 text-sm text-slate-900">
              {user.name || user.email}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {strings.profile.email}
            </dt>
            <dd className="mt-1 break-all text-sm text-slate-900">
              {user.email}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {strings.profile.role}
            </dt>
            <dd className="mt-1 text-sm text-slate-900">
              {strings.roles[user.role]}
            </dd>
          </div>
        </dl>

        <button
          type="button"
          onClick={handleLogout}
          className="mt-6 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          {strings.shell.logout}
        </button>
      </section>
    </>
  )
}
