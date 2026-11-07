import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '@/context/AuthContext'
import { strings } from '@/lib/strings'

/**
 * Página provisional de aterrizaje: permite probar el login real mientras
 * T5/T6 construyen el armazón y las rutas definitivas.
 */
export default function ProvisionalHome() {
  const { user, status, logout, refresh } = useAuth()
  const navigate = useNavigate()
  const [leaving, setLeaving] = useState(false)

  async function handleLogout() {
    setLeaving(true)
    try {
      await logout()
      navigate('/login', { replace: true })
    } finally {
      setLeaving(false)
    }
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

        {status === 'authenticated' && user ? (
          <div className="mt-4 space-y-4">
            <h1 className="text-2xl font-semibold text-slate-900">
              Hola, {user.name}
            </h1>
            <p className="text-sm text-slate-600">
              {user.email} · {user.role}
            </p>
            <p className="text-sm text-slate-500">{strings.auth.sessionReady}</p>
            <button
              type="button"
              disabled={leaving}
              onClick={() => void handleLogout()}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-70"
            >
              {strings.shell.logout}
            </button>
          </div>
        ) : null}
      </section>
    </main>
  )
}
