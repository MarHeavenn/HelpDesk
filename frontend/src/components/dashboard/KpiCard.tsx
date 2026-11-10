/** Indicador numérico del dashboard (RF-91). */
export default function KpiCard({
  label,
  value,
}: {
  label: string
  value: number
}) {
  return (
    <article
      aria-label={label}
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
        {value}
      </p>
    </article>
  )
}
