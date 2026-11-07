import { useEffect, useState, type ReactNode } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'

import { useAuth } from '@/context/AuthContext'
import { strings } from '@/lib/strings'
import Sidebar from '@/layout/Sidebar'
import Topbar from '@/layout/Topbar'

/**
 * Armazón compartido de las rutas protegidas (RF-70, RF-72, RF-79).
 * Acepta `children` para pruebas y composición; sin ellos renderiza el Outlet.
 */
export default function AppShell({ children }: { children?: ReactNode }) {
  const { user, status, logout, refresh } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [deniedNotice, setDeniedNotice] = useState(false)

  useEffect(() => {
    const state = location.state as { denied?: boolean } | null
    if (!state?.denied) return

    setDeniedNotice(true)
    navigate(`${location.pathname}${location.search}`, {
      replace: true,
      state: null,
    })
  }, [location, navigate])

  if (!user) return null

  async function handleLogout() {
    try {
      await logout()
    } finally {
      navigate('/login', { replace: true })
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <a
        href="#contenido-principal"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary focus:shadow"
      >
        {strings.app.skipToContent}
      </a>

      <div className="lg:flex lg:min-h-screen">
        <Sidebar role={user.role} />

        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <Topbar user={user} onLogout={handleLogout} />

          <main
            id="contenido-principal"
            className="flex-1 px-4 py-6 sm:px-6 lg:px-8"
          >
            <div className="mx-auto w-full max-w-7xl">
              {status === 'error' ? (
                <div
                  role="alert"
                  className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                >
                  <p>{strings.auth.sessionError}</p>
                  <button
                    type="button"
                    onClick={() => void refresh()}
                    className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-semibold text-amber-900 hover:bg-amber-100"
                  >
                    {strings.common.retry}
                  </button>
                </div>
              ) : null}

              {deniedNotice ? (
                <div
                  role="alert"
                  className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                >
                  <p>{strings.routes.denied}</p>
                  <button
                    type="button"
                    aria-label={strings.common.close}
                    onClick={() => setDeniedNotice(false)}
                    className="rounded p-1 text-amber-700 hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              ) : null}

              {children ?? <Outlet />}
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
