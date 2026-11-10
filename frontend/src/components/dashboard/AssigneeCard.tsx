import type { AssigneeCount } from '@/types/dashboard'
import { strings } from '@/lib/strings'

/** Carga por técnico, con la fila de tickets sin asignar (RF-87, RF-91). */
export default function AssigneeCard({ items }: { items: AssigneeCount[] }) {
  return (
    <section
      aria-label={strings.dashboard.byAssignee}
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-base font-semibold text-slate-900">
        {strings.dashboard.byAssignee}
      </h2>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-600">
          {strings.dashboard.noTechnicians}
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-slate-100">
          {items.map((item) => (
            <li
              key={item.technician?.id ?? 'sin-asignar'}
              className="flex items-center justify-between gap-3 py-2.5 text-sm"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span
                  aria-hidden="true"
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-xs font-semibold text-primary"
                >
                  {item.label.charAt(0).toUpperCase()}
                </span>
                <span className="truncate font-medium text-slate-700">
                  {item.label}
                </span>
              </span>
              <span className="whitespace-nowrap text-slate-500">
                {strings.dashboard.ticketsCount(item.count)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
