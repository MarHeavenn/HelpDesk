import { Link } from 'react-router-dom'

import PageHeader from '@/components/ui/PageHeader'
import { useAuth } from '@/context/AuthContext'
import AppShell from '@/layout/AppShell'
import { strings } from '@/lib/strings'

/**
 * Página provisional de aterrizaje: muestra el armazón con la sesión real
 * mientras T6 construye las rutas definitivas.
 */
export default function ProvisionalHome() {
  const { user, status, refresh } = useAuth()

  if (status === 'authenticated' && user) {
    return (
      <AppShell>
        <PageHeader
          title={strings.nav.dashboard}
          subtitle={strings.auth.sessionReady}
        />
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">
            Hola, {user.name}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {user.email} · {strings.roles[user.role]}
          </p>
        </section>
      </AppShell>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <section className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary">
          {strings.app.name}
        </p>

        {status === 'loading' ? (
          <p role="status" className="mt-4 text-sm text-slate-600">
            {strings.auth.checkingSession}
          </p>
        ) : null}

        {status === 'error' ? (
          <div className="mt-4 space-y-3">
            <p role="alert" className="text-sm text-red-700">
              {strings.auth.sessionError}
            </p>
            <button
              type="button"
              onClick={() => void refresh()}
              className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
            >
              {strings.common.retry}
            </button>
          </div>
        ) : null}

        {status === 'anonymous' ? (
          <div className="mt-4 space-y-3">
            <h1 className="text-2xl font-semibold text-slate-900">
              {strings.auth.noSession}
            </h1>
            <Link
              to="/login"
              className="inline-block text-sm font-semibold text-primary underline-offset-4 hover:underline"
            >
              {strings.auth.title}
            </Link>
          </div>
        ) : null}
      </section>
    </main>
  )
}
