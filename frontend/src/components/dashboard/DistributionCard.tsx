export interface DistributionItem {
  label: string
  count: number
}

/** Barras horizontales con etiqueta, conteo y porcentaje (RF-91, RF-92). */
export default function DistributionCard({
  title,
  items,
  total,
}: {
  title: string
  items: DistributionItem[]
  total: number
}) {
  return (
    <section
      aria-label={title}
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <ul className="mt-4 space-y-3">
        {items.map((item) => {
          const percentage =
            total > 0 ? Math.round((item.count / total) * 100) : 0
          return (
            <li key={item.label}>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-slate-700">{item.label}</span>
                <span className="whitespace-nowrap text-slate-500">
                  {item.count} · {percentage}%
                </span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-primary transition-[width]"
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
