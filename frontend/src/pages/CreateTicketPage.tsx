import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '@/api/httpClient'
import { ticketsApi, type TicketsApi } from '@/api/tickets.api'
import PageHeader from '@/components/ui/PageHeader'
import { useAuth } from '@/context/AuthContext'
import { strings } from '@/lib/strings'

const PRIORITIES = ['Crítica', 'Alta', 'Media', 'Baja'] as const
type Priority = (typeof PRIORITIES)[number]

const SLA_HOURS: Record<Priority, number> = {
  Crítica: 2,
  Alta: 4,
  Media: 12,
  Baja: 24,
}

interface FormErrors {
  title?: string
  description?: string
  form?: string
}

function validate(title: string, description: string): FormErrors {
  const errors: FormErrors = {}
  const cleanTitle = title.trim()
  const cleanDescription = description.trim()

  if (!cleanTitle) errors.title = strings.tickets.form.requiredTitle
  else if (cleanTitle.length < 5 || cleanTitle.length > 120) {
    errors.title = strings.tickets.form.shortTitle
  }
  if (!cleanDescription) errors.description = strings.tickets.form.requiredDescription
  else if (cleanDescription.length < 20) {
    errors.description = strings.tickets.form.shortDescription
  }
  return errors
}

function saveClientPriority(id: string, priority: Priority): void {
  try {
    localStorage.setItem(`helpdesk.ticketMeta.${id}`, JSON.stringify({ priority }))
  } catch {
    // El modo privado o una cuota llena no debe impedir crear el ticket.
  }
}

export default function CreateTicketPage({ api }: { api?: TicketsApi }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const tickets = api ?? ticketsApi
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<Priority>('Media')
  const [errors, setErrors] = useState<FormErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validate(title, description)
    setErrors(nextErrors)
    if (nextErrors.title || nextErrors.description) return

    setIsSubmitting(true)
    try {
      const created = await tickets.create({
        title: title.trim(),
        description: description.trim(),
      })
      if (user?.role === 'administrador' || user?.role === 'tecnico') {
        await tickets.setPriority(created.id, priority)
      } else {
        saveClientPriority(created.id, priority)
      }
      navigate('/mis-tickets', { replace: true })
    } catch (cause) {
      setErrors({
        form: cause instanceof ApiError ? cause.detail : strings.tickets.form.error,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <PageHeader
        title={strings.routes.titles['/tickets/nuevo']}
        subtitle={strings.tickets.form.subtitle}
      />
      <form
        noValidate
        onSubmit={handleSubmit}
        className="max-w-3xl space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        {errors.form ? (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {errors.form}
          </p>
        ) : null}

        <div>
          <label htmlFor="ticket-title" className="block text-sm font-semibold text-slate-800">
            {strings.tickets.form.titleLabel}
          </label>
          <input
            id="ticket-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            aria-invalid={Boolean(errors.title)}
            aria-describedby={errors.title ? 'ticket-title-error' : undefined}
            placeholder={strings.tickets.form.titlePlaceholder}
            className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
          {errors.title ? <p id="ticket-title-error" className="mt-1 text-sm text-red-700">{errors.title}</p> : null}
        </div>

        <div>
          <label htmlFor="ticket-description" className="block text-sm font-semibold text-slate-800">
            {strings.tickets.form.descriptionLabel}
          </label>
          <textarea
            id="ticket-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            aria-invalid={Boolean(errors.description)}
            aria-describedby={errors.description ? 'ticket-description-error' : undefined}
            placeholder={strings.tickets.form.descriptionPlaceholder}
            rows={6}
            className="mt-2 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
          {errors.description ? <p id="ticket-description-error" className="mt-1 text-sm text-red-700">{errors.description}</p> : null}
        </div>

        <div>
          <label htmlFor="ticket-priority" className="block text-sm font-semibold text-slate-800">
            {strings.tickets.form.priorityLabel}
          </label>
          <select
            id="ticket-priority"
            value={priority}
            onChange={(event) => setPriority(event.target.value as Priority)}
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 sm:max-w-xs"
          >
            {PRIORITIES.map((option) => (
              <option key={option} value={option}>
                {strings.tickets.form.priorities[option]}
              </option>
            ))}
          </select>
          <p className="mt-1 text-sm text-slate-500">{strings.tickets.form.priorityHelp(SLA_HOURS[priority])}</p>
        </div>

        <div className="flex flex-wrap justify-end gap-3 border-t border-slate-100 pt-5">
          <Link
            to="/mis-tickets"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            {strings.tickets.form.cancel}
          </Link>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? strings.tickets.form.creating : strings.tickets.form.create}
          </button>
        </div>
      </form>
    </>
  )
}
