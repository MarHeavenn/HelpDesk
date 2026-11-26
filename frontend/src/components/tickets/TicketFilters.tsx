import { useEffect, useId, useRef, useState } from 'react'
import { Search } from 'lucide-react'

import {
  clearTicketFilters,
  hasActiveTicketFilters,
  TICKET_SLA_STATUSES,
  TICKET_SORTS,
  type TicketFilters as Filters,
  type TicketSort,
} from '@/lib/tickets'
import { strings } from '@/lib/strings'
import { PRIORITIES, STATUSES } from '@/types/ticket'

const SELECT_CLASS =
  'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30'

/** Búsqueda con debounce y filtros combinables del listado (RF-119). */
export default function TicketFilters({
  filters,
  onChange,
  technicians,
  showTechnician,
}: {
  filters: Filters
  onChange: (next: Filters) => void
  technicians: { id: string; name: string }[]
  showTechnician: boolean
}) {
  const fieldId = useId()
  const [search, setSearch] = useState(filters.query)
  const [requester, setRequester] = useState(filters.requester)
  const [lastQuery, setLastQuery] = useState(filters.query)
  const [lastRequester, setLastRequester] = useState(filters.requester)
  const onChangeRef = useRef(onChange)
  const filtersRef = useRef(filters)

  // Sincroniza los textos durante el render cuando la URL cambia por otra vía
  // (atrás, limpiar desde el vacío), antes de que el debounce pueda reescribirlos.
  if (lastQuery !== filters.query) {
    setLastQuery(filters.query)
    setSearch(filters.query)
  }
  if (lastRequester !== filters.requester) {
    setLastRequester(filters.requester)
    setRequester(filters.requester)
  }

  useEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])

  useEffect(() => {
    filtersRef.current = filters
  }, [filters])

  // Debounce de 300 ms: solo actualiza la URL cuando el término es estable.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const current = filtersRef.current
      const query = search.trim()
      if (query !== current.query) {
        onChangeRef.current({ ...current, query, page: 1 })
      }
    }, 300)
    return () => window.clearTimeout(timer)
  }, [search, filters.query])

  // El solicitante es un campo libre, sin directorio ni llamadas adicionales.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const current = filtersRef.current
      const value = requester.trim()
      if (value !== current.requester) {
        onChangeRef.current({ ...current, requester: value, page: 1 })
      }
    }, 300)
    return () => window.clearTimeout(timer)
  }, [requester, filters.requester])

  function update(patch: Partial<Filters>) {
    onChange({ ...filters, ...patch, page: 1 })
  }

  return (
    <section
      aria-label={strings.tickets.filtersLabel}
      className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2 lg:col-span-1">
          <label
            htmlFor={`${fieldId}-search`}
            className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
          >
            {strings.tickets.searchLabel}
          </label>
          <div className="relative mt-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              id={`${fieldId}-search`}
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={strings.tickets.searchPlaceholder}
              className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor={`${fieldId}-requester`}
            className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
          >
            {strings.tickets.requesterFilter}
          </label>
          <input
            id={`${fieldId}-requester`}
            type="search"
            value={requester}
            onChange={(event) => setRequester(event.target.value)}
            placeholder={strings.tickets.requesterPlaceholder}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30"
          />
        </div>

        <div>
          <label
            htmlFor={`${fieldId}-priority`}
            className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
          >
            {strings.tickets.priorityFilter}
          </label>
          <select
            id={`${fieldId}-priority`}
            value={filters.priority}
            onChange={(event) => update({ priority: event.target.value })}
            className={SELECT_CLASS}
          >
            <option value="all">{strings.tickets.all}</option>
            {PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {priority}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor={`${fieldId}-status`}
            className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
          >
            {strings.tickets.statusFilter}
          </label>
          <select
            id={`${fieldId}-status`}
            value={filters.status}
            onChange={(event) => update({ status: event.target.value })}
            className={SELECT_CLASS}
          >
            <option value="all">{strings.tickets.all}</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>

        {showTechnician ? (
          <div>
            <label
              htmlFor={`${fieldId}-assignee`}
              className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
            >
              {strings.tickets.assigneeFilter}
            </label>
            <select
              id={`${fieldId}-assignee`}
              value={filters.assignee}
              onChange={(event) => update({ assignee: event.target.value })}
              className={SELECT_CLASS}
            >
              <option value="all">{strings.tickets.all}</option>
              <option value="unassigned">{strings.tickets.unassigned}</option>
              {technicians.map((technician) => (
                <option key={technician.id} value={technician.id}>
                  {technician.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div>
          <label
            htmlFor={`${fieldId}-sla`}
            className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
          >
            {strings.tickets.slaFilter}
          </label>
          <select
            id={`${fieldId}-sla`}
            value={filters.sla}
            onChange={(event) => update({ sla: event.target.value })}
            className={SELECT_CLASS}
          >
            <option value="all">{strings.tickets.all}</option>
            <option value="none">{strings.tickets.noSla}</option>
            {TICKET_SLA_STATUSES.map((sla) => (
              <option key={sla} value={sla}>
                {strings.tickets.slaStatus[sla]}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor={`${fieldId}-sort`}
            className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
          >
            {strings.tickets.sortLabel}
          </label>
          <select
            id={`${fieldId}-sort`}
            value={filters.sort}
            onChange={(event) =>
              update({ sort: event.target.value as TicketSort })
            }
            className={SELECT_CLASS}
          >
            {TICKET_SORTS.map((sort) => (
              <option key={sort} value={sort}>
                {strings.tickets.sorts[sort]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {hasActiveTicketFilters(filters) ? (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => {
              setSearch('')
              setRequester('')
              onChange(clearTicketFilters(filters))
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            {strings.tickets.clear}
          </button>
        </div>
      ) : null}
    </section>
  )
}
