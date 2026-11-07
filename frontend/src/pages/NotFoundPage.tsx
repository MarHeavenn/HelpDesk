import { Link } from 'react-router-dom'

import PageHeader from '@/components/ui/PageHeader'
import { useAuth } from '@/context/AuthContext'
import { firstAllowedRoute } from '@/lib/permissions'
import { strings } from '@/lib/strings'

/** 404 dentro del armazón, con enlace de salida (RF-69, RF-73). */
export default function NotFoundPage() {
  const { user } = useAuth()
  const fallback = user ? firstAllowedRoute(user.role) : '/login'

  return (
    <>
      <PageHeader title={strings.routes.notFoundTitle} />
      <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center">
        <p className="text-sm text-slate-600">{strings.routes.notFoundBody}</p>
        <Link
          to={fallback}
          className="mt-4 inline-block text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          {strings.routes.backToApp}
        </Link>
      </section>
    </>
  )
}
