import { useId, useState } from 'react'

import type { UnassignedAccount } from '@/api/companies.api'
import { strings } from '@/lib/strings'

import { FIELD_CLASS, LABEL_CLASS, PRIMARY_BUTTON } from './styles'

/** Asociación de una cuenta sin empresa elegida del listado de RF-140. */
export default function CompanyAssociationPanel({
  accounts,
  loading,
  pending,
  onAssociate,
}: {
  accounts: UnassignedAccount[]
  loading: boolean
  pending: boolean
  onAssociate: (accountId: string) => void
}) {
  const fieldId = useId()
  const [accountId, setAccountId] = useState('')

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {strings.companies.association.title}
      </h3>
      {loading ? (
        <p className="mt-2 text-sm text-slate-600">{strings.common.loading}</p>
      ) : accounts.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">
          {strings.companies.association.empty}
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="min-w-[14rem] flex-1">
            <label htmlFor={`${fieldId}-account`} className={LABEL_CLASS}>
              {strings.companies.association.label}
            </label>
            <select
              id={`${fieldId}-account`}
              value={accountId}
              onChange={(event) => setAccountId(event.target.value)}
              className={FIELD_CLASS}
            >
              <option value="">{strings.companies.noValue}</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {`${account.name} · ${account.email}`}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => onAssociate(accountId)}
            disabled={pending || !accountId}
            className={PRIMARY_BUTTON}
          >
            {pending
              ? strings.companies.association.saving
              : strings.companies.association.submit}
          </button>
        </div>
      )}
    </div>
  )
}
