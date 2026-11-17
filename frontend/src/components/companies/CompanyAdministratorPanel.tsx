import { useId, useState, type FormEvent } from 'react'

import type { CompanyAdministratorPayload } from '@/api/companies.api'
import { strings } from '@/lib/strings'

import {
  FIELD_CLASS,
  FORM_ERROR_CLASS,
  LABEL_CLASS,
  PRIMARY_BUTTON,
} from './styles'

/**
 * Acción única de RF-141: invitar cuando no hay administrador y reenviar
 * cuando la invitación está pendiente. Nunca muestra token, enlace ni hash.
 */
export default function CompanyAdministratorPanel({
  hasAdministrator,
  invitationPending,
  pending,
  onInvite,
  onResend,
}: {
  hasAdministrator: boolean
  invitationPending: boolean
  pending: boolean
  onInvite: (payload: CompanyAdministratorPayload) => void
  onResend: () => void
}) {
  const fieldId = useId()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (hasAdministrator) {
    return (
      <p className="text-sm text-slate-600">
        {strings.companies.administrator.present}
      </p>
    )
  }

  if (invitationPending) {
    return (
      <div>
        <p className="text-sm text-slate-600">
          {strings.companies.administrator.pending}
        </p>
        <button
          type="button"
          onClick={onResend}
          disabled={pending}
          className={`${PRIMARY_BUTTON} mt-2`}
        >
          {pending
            ? strings.companies.administrator.inviting
            : strings.companies.administrator.resend}
        </button>
      </div>
    )
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedName = name.trim()
    const trimmedEmail = email.trim()
    if (!trimmedName || !trimmedEmail) {
      setError(strings.companies.form.requiredAdministrator)
      return
    }
    setError(null)
    onInvite({ name: trimmedName, email: trimmedEmail })
  }

  return (
    <div>
      <p className="text-sm text-slate-600">
        {strings.companies.administrator.none}
      </p>
      {open ? (
        <form noValidate onSubmit={handleSubmit} className="mt-3 space-y-3">
          <div>
            <label
              htmlFor={`${fieldId}-name`}
              className={LABEL_CLASS}
            >
              {strings.companies.form.administratorName}
            </label>
            <input
              id={`${fieldId}-name`}
              value={name}
              onChange={(event) => setName(event.target.value)}
              className={FIELD_CLASS}
            />
          </div>
          <div>
            <label
              htmlFor={`${fieldId}-email`}
              className={LABEL_CLASS}
            >
              {strings.companies.form.administratorEmail}
            </label>
            <input
              id={`${fieldId}-email`}
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={FIELD_CLASS}
            />
          </div>
          {error ? (
            <p role="alert" className={FORM_ERROR_CLASS}>
              {error}
            </p>
          ) : null}
          <button type="submit" disabled={pending} className={PRIMARY_BUTTON}>
            {pending
              ? strings.companies.administrator.inviting
              : strings.companies.administrator.submitInvite}
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className={`${PRIMARY_BUTTON} mt-2`}
        >
          {strings.companies.administrator.invite}
        </button>
      )}
    </div>
  )
}
