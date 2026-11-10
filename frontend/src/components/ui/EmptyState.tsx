import type { ReactNode } from 'react'

/** Estado vacío reutilizable para listados y paneles (RF-92, RF-103). */
export default function EmptyState({
  title,
  message,
  action,
}: {
  title: string
  message: string
  action?: ReactNode
}) {
  return (
    <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-slate-600">{message}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </section>
  )
}
