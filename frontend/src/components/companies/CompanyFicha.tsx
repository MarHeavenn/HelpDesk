import { useId, type ReactNode } from 'react'

import {
  COMPANY_TICKET_STATUSES,
  type CompanySummary,
} from '@/api/companies.api'
import { formatTicketDate } from '@/lib/dates'
import { strings } from '@/lib/strings'

import { CARD_CLASS } from './styles'

/** Ficha de RF-143: datos y agregados, sin cuentas ni identificadores ajenos. */
export default function CompanyFicha({
  company,
  children,
}: {
  company: CompanySummary
  children?: ReactNode
}) {
  const titleId = useId()
  const empty = strings.companies.noValue
  const active = company.status === 'active'

  return (
    <section aria-labelledby={titleId} className={CARD_CLASS}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id={titleId} className="text-lg font-semibold text-slate-900">
            {strings.companies.fichaTitle}
          </h2>
          <p className="mt-1 text-xl font-semibold text-slate-900">
            {company.name}
          </p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
            active
              ? 'bg-emerald-50 text-emerald-700'
              : 'bg-slate-100 text-slate-600'
          }`}
        >
          {strings.companies.status[company.status]}
        </span>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {strings.companies.fields.email}
          </dt>
          <dd className="mt-0.5 text-slate-800">{company.email ?? empty}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {strings.companies.fields.phone}
          </dt>
          <dd className="mt-0.5 text-slate-800">{company.phone ?? empty}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {strings.companies.fields.contactName}
          </dt>
          <dd className="mt-0.5 text-slate-800">
            {company.contact_name ?? empty}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {strings.companies.fields.createdAt}
          </dt>
          <dd className="mt-0.5 text-slate-800">
            {formatTicketDate(company.created_at)}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {strings.companies.fields.usersTotal}
          </dt>
          <dd className="mt-0.5 text-slate-800">{company.users_total}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {strings.companies.fields.ticketsTotal}
          </dt>
          <dd className="mt-0.5 text-slate-800">{company.tickets_total}</dd>
        </div>
      </dl>

      <div className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          {strings.companies.ticketsByStatus}
        </h3>
        <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          {COMPANY_TICKET_STATUSES.map((status) => (
            <div
              key={status}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"
            >
              <dt className="text-xs text-slate-500">{status}</dt>
              <dd className="text-base font-semibold text-slate-900">
                {company.tickets_by_status[status] ?? 0}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {children ? <div className="mt-5 space-y-4">{children}</div> : null}
    </section>
  )
}
