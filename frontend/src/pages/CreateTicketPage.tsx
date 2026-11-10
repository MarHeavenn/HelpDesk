import { useId, useRef, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import PageHeader from '@/components/ui/PageHeader'
import { ApiError } from '@/api/httpClient'
import { ticketsApi, type TicketsApi } from '@/api/tickets.api'
import { useAuth } from '@/context/AuthContext'
import {
  canReadSlaPolicies,
  canSetTicketPriority,
  firstAllowedRoute,
} from '@/lib/permissions'
import { strings } from '@/lib/strings'
import {
  DEFAULT_PRIORITY,
  PRIORITIES,
  type Priority,
} from '@/types/ticket'
import {
  codePointLength,
  DESCRIPTION_MAX_LENGTH,
  formatTargetHours,
  TITLE_MAX_LENGTH,
  validateTicketFields,
  type TicketFieldErrors,
} from '@/lib/ticketForm'

/** Alta real de tickets con `POST /api/tickets` (HU-02, HU-03, RF-55). */
export default function CreateTicketPage({ api = ticketsApi }: { api?: TicketsApi }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const fieldId = useId()

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<Priority>(DEFAULT_PRIORITY)
  const [errors, setErrors] = useState<TicketFieldErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirmingDiscard, setConfirmingDiscard] = useState(false)

  const titleRef = useRef<HTMLInputElement>(null)
  const descriptionRef = useRef<HTMLTextAreaElement>(null)
  const discardRef = useRef<HTMLButtonElement>(null)

  const role = user?.role
  const canSetPriority = role ? canSetTicketPriority(role) : false
  const canReadPolicies = role ? canReadSlaPolicies(role) : false
  const policies = useQuery({
    queryKey: ['sla', 'policies'],
    queryFn: () => api.getSlaPolicies(),
    enabled: canReadPolicies,
    retry: false,
  })

  const dirty = title.trim().length > 0 || description.trim().length > 0
  const fallback = role ? firstAllowedRoute(role) : '/login'

  const titleErrorId = `${fieldId}-title-error`
  const titleHelpId = `${fieldId}-title-help`
  const descriptionErrorId = `${fieldId}-description-error`
  const descriptionHelpId = `${fieldId}-description-help`

  const targetHours = Array.isArray(policies.data)
    ? policies.data.find((policy) => policy.priority === priority)?.hours
    : undefined

  function focusFirstError(next: TicketFieldErrors) {
    if (next.title) titleRef.current?.focus()
    else if (next.description) descriptionRef.current?.focus()
  }

  function handleCancel() {
    if (!dirty) {
      navigate(fallback)
      return
    }
    setConfirmingDiscard(true)
    requestAnimationFrame(() => discardRef.current?.focus())
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return

    const nextErrors = validateTicketFields(title, description)
    setErrors(nextErrors)
    setSubmitError(null)

    if (nextErrors.title || nextErrors.description) {
      focusFirstError(nextErrors)
      return
    }

    setSubmitting(true)

    try {
      const ticket = await api.createTicket({
        title: title.trim(),
        description: description.trim(),
      })

      let priorityError: string | undefined
      if (canSetPriority) {
        try {
          await api.setPriority(ticket.id, priority)
        } catch (cause) {
          priorityError =
            cause instanceof ApiError
              ? cause.detail
              : strings.createTicket.networkError
        }
      }

      navigate('/mis-tickets', {
        replace: true,
        state: {
          createdTicketId: ticket.id,
          ...(priorityError ? { priorityError } : {}),
        },
      })
    } catch (cause) {
      setSubmitError(
        cause instanceof ApiError && cause.status === 422
          ? cause.detail
          : strings.createTicket.networkError,
      )
      setSubmitting(false)
    }
  }

  return (
    <>
      <PageHeader
        title={strings.routes.titles['/tickets/nuevo']}
        subtitle={strings.createTicket.subtitle}
      />

      <form
        noValidate
        onSubmit={handleSubmit}
        className="max-w-3xl space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            {strings.createTicket.cardTitle}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {strings.createTicket.cardSubtitle}
          </p>
        </div>

        <div>
          <label
            htmlFor={`${fieldId}-title`}
            className="block text-sm font-medium text-slate-700"
          >
            {strings.createTicket.title}
          </label>
          <input
            id={`${fieldId}-title`}
            ref={titleRef}
            type="text"
            value={title}
            maxLength={TITLE_MAX_LENGTH + 1}
            onChange={(event) => setTitle(event.target.value)}
            aria-invalid={Boolean(errors.title)}
            aria-describedby={`${
              errors.title ? `${titleErrorId} ` : ''
            }${titleHelpId}`}
            placeholder={strings.createTicket.titlePlaceholder}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30 aria-[invalid=true]:border-red-500"
          />
          <p id={titleHelpId} className="mt-1 text-xs text-slate-500">
            {strings.createTicket.titleHelp} {codePointLength(title.trim())}/
            {TITLE_MAX_LENGTH}
          </p>
          {errors.title ? (
            <p id={titleErrorId} role="alert" className="mt-1 text-sm text-red-700">
              {errors.title}
            </p>
          ) : null}
        </div>

        <div>
          <label
            htmlFor={`${fieldId}-description`}
            className="block text-sm font-medium text-slate-700"
          >
            {strings.createTicket.description}
          </label>
          <textarea
            id={`${fieldId}-description`}
            ref={descriptionRef}
            value={description}
            rows={6}
            maxLength={DESCRIPTION_MAX_LENGTH + 1}
            onChange={(event) => setDescription(event.target.value)}
            aria-invalid={Boolean(errors.description)}
            aria-describedby={`${
              errors.description ? `${descriptionErrorId} ` : ''
            }${descriptionHelpId}`}
            placeholder={strings.createTicket.descriptionPlaceholder}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30 aria-[invalid=true]:border-red-500"
          />
          <p id={descriptionHelpId} className="mt-1 text-xs text-slate-500">
            {strings.createTicket.descriptionHelp}{' '}
            {codePointLength(description.trim())}/{DESCRIPTION_MAX_LENGTH}
          </p>
          {errors.description ? (
            <p
              id={descriptionErrorId}
              role="alert"
              className="mt-1 text-sm text-red-700"
            >
              {errors.description}
            </p>
          ) : null}
        </div>

        {canSetPriority ? (
          <div>
            <label
              htmlFor={`${fieldId}-priority`}
              className="block text-sm font-medium text-slate-700"
            >
              {strings.createTicket.priority}
            </label>
            <select
              id={`${fieldId}-priority`}
              value={priority}
              onChange={(event) => setPriority(event.target.value as Priority)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30 sm:w-60"
            >
              {PRIORITIES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>

            {canReadPolicies ? (
              <p className="mt-1 text-xs text-slate-500" role="status">
                {policies.isPending
                  ? strings.createTicket.loadingSla
                  : targetHours !== undefined
                    ? strings.createTicket.target(
                        priority,
                        formatTargetHours(targetHours),
                      )
                    : null}
              </p>
            ) : null}
          </div>
        ) : null}

        <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
          {canSetPriority
            ? strings.createTicket.assignmentStaff
            : strings.createTicket.assignmentClient}
        </p>

        {submitError ? (
          <p
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            {submitError}
          </p>
        ) : null}

        {confirmingDiscard ? (
          <div
            role="alertdialog"
            aria-labelledby={`${fieldId}-discard-title`}
            aria-describedby={`${fieldId}-discard-body`}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setConfirmingDiscard(false)
            }}
            className="rounded-xl border border-amber-200 bg-amber-50 p-4"
          >
            <p
              id={`${fieldId}-discard-title`}
              className="text-sm font-semibold text-amber-900"
            >
              {strings.createTicket.discardTitle}
            </p>
            <p
              id={`${fieldId}-discard-body`}
              className="mt-1 text-sm text-amber-800"
            >
              {strings.createTicket.discardBody}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                ref={discardRef}
                type="button"
                onClick={() => navigate(fallback)}
                className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-semibold text-amber-900 hover:bg-amber-100"
              >
                {strings.createTicket.discardConfirm}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDiscard(false)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                {strings.createTicket.keepEditing}
              </button>
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting
              ? strings.createTicket.submitting
              : strings.createTicket.submit}
          </button>
          <button
            type="button"
            onClick={handleCancel}
            disabled={submitting}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {strings.common.cancel}
          </button>
        </div>
      </form>
    </>
  )
}
