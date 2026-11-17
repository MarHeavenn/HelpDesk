import { useId, useState, type FormEvent } from 'react'

import type { CreateCompanyPayload } from '@/api/companies.api'
import { strings } from '@/lib/strings'

import {
  CARD_CLASS,
  FIELD_CLASS,
  FORM_ERROR_CLASS,
  LABEL_CLASS,
  PRIMARY_BUTTON,
} from './styles'

/** Alta de empresa con administrador inicial opcional (RF-126, RF-135). */
export default function CompanyCreateForm({
  pending,
  onSubmit,
}: {
  pending: boolean
  onSubmit: (payload: CreateCompanyPayload) => void
}) {
  const fieldId = useId()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [contactName, setContactName] = useState('')
  const [withAdministrator, setWithAdministrator] = useState(false)
  const [administratorName, setAdministratorName] = useState('')
  const [administratorEmail, setAdministratorEmail] = useState('')
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedName = name.trim()
    const trimmedEmail = email.trim()
    if (!trimmedName) {
      setError(strings.companies.form.requiredName)
      return
    }
    if (!trimmedEmail) {
      setError(strings.companies.form.requiredEmail)
      return
    }

    let administrator: CreateCompanyPayload['administrator'] = null
    if (withAdministrator) {
      const adminName = administratorName.trim()
      const adminEmail = administratorEmail.trim()
      if (!adminName || !adminEmail) {
        setError(strings.companies.form.requiredAdministrator)
        return
      }
      administrator = { name: adminName, email: adminEmail }
    }

    setError(null)
    onSubmit({
      name: trimmedName,
      email: trimmedEmail,
      phone: phone.trim() || null,
      contact_name: contactName.trim() || null,
      administrator,
    })
  }

  return (
    <section aria-labelledby={`${fieldId}-title`} className={CARD_CLASS}>
      <h2
        id={`${fieldId}-title`}
        className="text-lg font-semibold text-slate-900"
      >
        {strings.companies.create.title}
      </h2>
      <form noValidate onSubmit={handleSubmit} className="mt-3 space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor={`${fieldId}-name`} className={LABEL_CLASS}>
              {strings.companies.form.name}
            </label>
            <input
              id={`${fieldId}-name`}
              value={name}
              onChange={(event) => setName(event.target.value)}
              className={FIELD_CLASS}
            />
          </div>
          <div>
            <label htmlFor={`${fieldId}-email`} className={LABEL_CLASS}>
              {strings.companies.form.email}
            </label>
            <input
              id={`${fieldId}-email`}
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={FIELD_CLASS}
            />
          </div>
          <div>
            <label htmlFor={`${fieldId}-phone`} className={LABEL_CLASS}>
              {strings.companies.form.phone}
            </label>
            <input
              id={`${fieldId}-phone`}
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className={FIELD_CLASS}
            />
          </div>
          <div>
            <label htmlFor={`${fieldId}-contact`} className={LABEL_CLASS}>
              {strings.companies.form.contactName}
            </label>
            <input
              id={`${fieldId}-contact`}
              value={contactName}
              onChange={(event) => setContactName(event.target.value)}
              className={FIELD_CLASS}
            />
          </div>
        </div>

        <div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={withAdministrator}
              onChange={(event) => setWithAdministrator(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
            />
            {strings.companies.create.withAdministrator}
          </label>
        </div>

        {withAdministrator ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor={`${fieldId}-admin-name`} className={LABEL_CLASS}>
                {strings.companies.form.administratorName}
              </label>
              <input
                id={`${fieldId}-admin-name`}
                value={administratorName}
                onChange={(event) => setAdministratorName(event.target.value)}
                className={FIELD_CLASS}
              />
            </div>
            <div>
              <label htmlFor={`${fieldId}-admin-email`} className={LABEL_CLASS}>
                {strings.companies.form.administratorEmail}
              </label>
              <input
                id={`${fieldId}-admin-email`}
                type="email"
                value={administratorEmail}
                onChange={(event) => setAdministratorEmail(event.target.value)}
                className={FIELD_CLASS}
              />
            </div>
          </div>
        ) : null}

        {error ? (
          <p role="alert" className={FORM_ERROR_CLASS}>
            {error}
          </p>
        ) : null}

        <button type="submit" disabled={pending} className={PRIMARY_BUTTON}>
          {pending
            ? strings.companies.create.submitting
            : strings.companies.create.submit}
        </button>
      </form>
    </section>
  )
}
