import { AlertTriangle } from 'lucide-react'

/** Estado de error con reintento explícito (RF-92, RF-103). */
export default function ErrorState({
  title,
  message,
  retryLabel,
  onRetry,
}: {
  title: string
  message: string
  retryLabel: string
  onRetry: () => void
}) {
  return (
    <section
      role="alert"
      className="rounded-2xl border border-red-200 bg-white p-8 text-center shadow-sm"
    >
      <AlertTriangle
        className="mx-auto h-8 w-8 text-red-500"
        aria-hidden="true"
      />
      <h2 className="mt-2 text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-slate-600">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
      >
        {retryLabel}
      </button>
    </section>
  )
}
