/** Indicador numérico del dashboard (RF-91, RF-128). */
export default function KpiCard({
  label,
  value,
  hint,
}: {
  label: string
  value: number
  hint?: { text: string; tone?: 'warning' }
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
      {hint ? (
        <p
          className={`mt-1 text-xs font-medium ${
            hint.tone === 'warning' ? 'text-amber-700' : 'text-slate-500'
          }`}
        >
          {hint.text}
        </p>
      ) : null}
    </article>
  )
}
