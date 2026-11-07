import type { ReactNode } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '@/context/AuthContext'
import { strings } from '@/lib/strings'
import Sidebar from '@/layout/Sidebar'
import Topbar from '@/layout/Topbar'

/**
 * Armazón compartido de las rutas protegidas (RF-70, RF-72, RF-79).
 * Acepta `children` para pruebas y composición; sin ellos renderiza el Outlet.
 */
export default function AppShell({ children }: { children?: ReactNode }) {
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
              {children ?? <Outlet />}
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
