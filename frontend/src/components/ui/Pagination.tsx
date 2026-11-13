import { strings } from '@/lib/strings'

function pageNumbers(page: number, pages: number): number[] {
  const visible = 5
  let start = Math.max(1, page - Math.floor(visible / 2))
  const end = Math.min(pages, start + visible - 1)
  start = Math.max(1, end - visible + 1)
  return Array.from({ length: end - start + 1 }, (_, index) => start + index)
}

/** Paginación accesible del listado (RF-119). */
export default function Pagination({
  page,
  pages,
  onChange,
}: {
  page: number
  pages: number
  onChange: (page: number) => void
}) {
  if (pages <= 1) return null

  return (
    <nav
      aria-label={strings.tickets.pagination.label}
      className="flex flex-wrap items-center justify-center gap-1"
    >
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {strings.tickets.pagination.previous}
      </button>
      {pageNumbers(page, pages).map((number) => (
        <button
          key={number}
          type="button"
          onClick={() => onChange(number)}
          aria-label={strings.tickets.pagination.page(number)}
          aria-current={number === page ? 'page' : undefined}
          className={`rounded-lg border px-3 py-1.5 text-sm font-semibold transition ${
            number === page
              ? 'border-primary bg-primary text-white'
              : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
          }`}
        >
          {number}
        </button>
      ))}
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page >= pages}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {strings.tickets.pagination.next}
      </button>
    </nav>
  )
}
