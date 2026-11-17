import { useEffect, useId, useState, type FormEvent } from 'react'

import type {
  CompanySummary,
  UpdateCompanyPayload,
} from '@/api/companies.api'
import { strings } from '@/lib/strings'

import {
  CARD_CLASS,
  FIELD_CLASS,
  FORM_ERROR_CLASS,
  LABEL_CLASS,
  PRIMARY_BUTTON,
} from './styles'

/** Actualización de datos de la empresa (RF-131, RF-142). */
export default function CompanyEditForm({
  company,
  pending,
  onSubmit,
}: {
  company: CompanySummary
  pending: boolean
  onSubmit: (payload: UpdateCompanyPayload) => void
}) {
  const fieldId = useId()
  const [name, setName] = useState(company.name)
  const [email, setEmail] = useState(company.email ?? '')
  const [phone, setPhone] = useState(company.phone ?? '')
  const [contactName, setContactName] = useState(company.contact_name ?? '')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setName(company.name)
    setEmail(company.email ?? '')
    setPhone(company.phone ?? '')
    setContactName(company.contact_name ?? '')
    setError(null)
  }, [
    company.id,
    company.name,
    company.email,
    company.phone,
    company.contact_name,
  ])

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedName = name.trim()
    if (!trimmedName) {
      setError(strings.companies.form.requiredName)
      return
    }

    const payload: UpdateCompanyPayload = {}
    if (trimmedName !== company.name) payload.name = trimmedName

    const trimmedEmail = email.trim()
    if (trimmedEmail && trimmedEmail !== (company.email ?? '')) {
      payload.email = trimmedEmail
    }

    const trimmedPhone = phone.trim()
    if (trimmedPhone !== (company.phone ?? '')) {
      payload.phone = trimmedPhone || null
    }

    const trimmedContact = contactName.trim()
    if (trimmedContact !== (company.contact_name ?? '')) {
      payload.contact_name = trimmedContact || null
    }

    if (Object.keys(payload).length === 0) {
      setError(strings.companies.edit.noChanges)
      return
    }

    setError(null)
    onSubmit(payload)
  }

  return (
    <section aria-labelledby={`${fieldId}-title`} className={CARD_CLASS}>
      <h2
        id={`${fieldId}-title`}
        className="text-lg font-semibold text-slate-900"
      >
        {strings.companies.edit.title}
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

        {error ? (
          <p role="alert" className={FORM_ERROR_CLASS}>
            {error}
          </p>
        ) : null}

        <button type="submit" disabled={pending} className={PRIMARY_BUTTON}>
          {pending
            ? strings.companies.edit.submitting
            : strings.companies.edit.submit}
        </button>
      </form>
    </section>
  )
}
