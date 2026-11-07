import { Link } from 'react-router-dom'

import PageHeader from '@/components/ui/PageHeader'
import { useAuth } from '@/context/AuthContext'
import { firstAllowedRoute } from '@/lib/permissions'
import { strings } from '@/lib/strings'

/** Vista marcador para secciones aún sin contenido real (RF-78). */
export default function PlaceholderPage({
  title,
  subtitle,
}: {
  title: string
  subtitle?: string
}) {
  const { user } = useAuth()
  const fallback = user ? firstAllowedRoute(user.role) : '/login'

  return (
    <>
      <PageHeader title={title} subtitle={subtitle} />
      <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <h2 className="text-lg font-semibold text-slate-900">
          {strings.routes.comingSoon}
        </h2>
        <p className="mx-auto mt-1 max-w-md text-sm text-slate-600">
          {strings.routes.comingSoonBody}
        </p>
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
