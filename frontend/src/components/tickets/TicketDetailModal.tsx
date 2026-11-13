import { useEffect, useId, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { ApiError } from '@/api/httpClient'
import { ticketsApi, type TicketsApi } from '@/api/tickets.api'
import { PriorityBadge, StatusBadge } from '@/components/ui/Badges'
import ErrorState from '@/components/ui/ErrorState'
import Modal from '@/components/ui/Modal'
import Skeleton from '@/components/ui/Skeleton'
import { useAuth } from '@/context/AuthContext'
import {
  ticketKeys,
  useTechnicians,
  useTicketComments,
  useTicketDetail,
} from '@/hooks/useTickets'
import { formatTicketDate } from '@/lib/dates'
import { friendlyTicketId } from '@/lib/format'
import {
  canAssignTicket,
  canChangeTicketStatus,
  canCommentTicket,
} from '@/lib/permissions'
import { strings } from '@/lib/strings'
import { formatTargetMinutes } from '@/lib/tickets'
import {
  PRIORITIES,
  STATUS_TRANSITIONS,
  type TicketStatus,
} from '@/types/ticket'

const SELECT_CLASS =
  'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500'

const PRIMARY_BUTTON =
  'rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white transition hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60'

const COMMENT_MAX_LENGTH = 2000

function countCodePoints(value: string): number {
  return Array.from(value).length
}

/** Detalle completo con acciones y seguimiento (HU-22, RF-109 a RF-111). */
export default function TicketDetailModal({
  ticketId,
  onClose,
  api = ticketsApi,
}: {
  ticketId: string | null
  onClose: () => void
  api?: TicketsApi
}) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const fieldId = useId()

  const detail = useTicketDetail(ticketId, api)
  const comments = useTicketComments(ticketId, api)
  const ticket = detail.data

  const role = user?.role
  const canEdit = role ? canChangeTicketStatus(role) : false
  const canAssign = role ? canAssignTicket(role) : false
  const canComment = role ? canCommentTicket(role) : false

  const technicians = useTechnicians(api, Boolean(ticketId) && canAssign)

  const [priority, setPriority] = useState('')
  const [status, setStatus] = useState('')
  const [assignee, setAssignee] = useState('')
  const [comment, setComment] = useState('')
  const [commentError, setCommentError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [commentPending, setCommentPending] = useState(false)

  useEffect(() => {
    setComment('')
    setCommentError(null)
    setActionError(null)
    setActionMessage(null)
    setPending(null)
  }, [ticketId])

  useEffect(() => {
    if (!ticket) return
    setPriority(ticket.priority ?? '')
    setStatus(ticket.status)
    setAssignee(ticket.assignee?.id ?? '')
  }, [ticket])

  const closed = ticket?.status === 'Cerrado'
  const transitions =
    ticket && ticket.status in STATUS_TRANSITIONS
      ? STATUS_TRANSITIONS[ticket.status as TicketStatus]
      : []

  function actionFailure(cause: unknown): string {
    return cause instanceof ApiError
      ? cause.detail
      : strings.tickets.detail.networkError
  }

  async function runAction(name: string, action: () => Promise<unknown>) {
    setPending(name)
    setActionError(null)
    setActionMessage(null)
    try {
      await action()
      if (ticketId) {
        await queryClient.invalidateQueries({
          queryKey: ticketKeys.detail(ticketId),
        })
      }
      await queryClient.invalidateQueries({ queryKey: ticketKeys.lists })
      setActionMessage(strings.tickets.detail.actionSaved)
    } catch (cause) {
      setActionError(actionFailure(cause))
    } finally {
      setPending(null)
    }
  }

  async function handleStatus() {
    if (!ticket || status === ticket.status) return
    await runAction('status', () => api.setStatus(ticket.id, status))
  }

  async function handlePriority() {
    if (!ticket || priority === (ticket.priority ?? '')) return
    await runAction('priority', () => api.setPriority(ticket.id, priority))
  }

  async function handleAssignee() {
    if (!ticket || !assignee || assignee === ticket.assignee?.id) return
    await runAction('assignee', () => api.assign(ticket.id, assignee))
  }

  async function handleComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ticketId || commentPending) return
    const body = comment.trim()
    if (!body) {
      setCommentError(strings.tickets.detail.commentRequired)
      return
    }
    if (countCodePoints(body) > COMMENT_MAX_LENGTH) {
      setCommentError(strings.tickets.detail.commentTooLong)
      return
    }

    setCommentPending(true)
    setCommentError(null)
    setActionError(null)
    try {
      await api.addComment(ticketId, body)
      setComment('')
      await queryClient.invalidateQueries({
        queryKey: ticketKeys.comments(ticketId),
      })
      setActionMessage(strings.tickets.detail.commentAdded)
    } catch (cause) {
      setActionError(actionFailure(cause))
    } finally {
      setCommentPending(false)
    }
  }

  return (
    <Modal
      open={Boolean(ticketId)}
      title={strings.tickets.detail.title}
      onClose={onClose}
    >
      {detail.isPending ? (
        <div className="space-y-3" role="status" aria-label={strings.tickets.detail.loading}>
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : detail.isError || !ticket ? (
        <ErrorState
          title={strings.tickets.detail.errorTitle}
          message={strings.tickets.detail.errorBody}
          retryLabel={strings.common.retry}
          onRetry={() => void detail.refetch()}
        />
      ) : (
        <div className="space-y-5">
          <div>
            <p className="font-mono text-xs text-slate-500">
              {friendlyTicketId(ticket.id)}
            </p>
            <h3 className="mt-1 text-xl font-semibold text-slate-900">
              {ticket.title}
            </h3>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={ticket.status} />
              <PriorityBadge priority={ticket.priority} />
              <span className="text-sm text-slate-600">
                {ticket.assignee?.name ?? strings.tickets.unassigned}
              </span>
            </div>
          </div>

          <dl className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {strings.tickets.detail.requester}
              </dt>
              <dd className="mt-0.5 text-slate-800">
                {ticket.requester
                  ? `${ticket.requester.name} · ${ticket.requester.email}`
                  : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {strings.tickets.detail.created}
              </dt>
              <dd className="mt-0.5 text-slate-800">
                {formatTicketDate(ticket.created_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {strings.tickets.detail.resolved}
              </dt>
              <dd className="mt-0.5 text-slate-800">
                {ticket.resolved_at
                  ? formatTicketDate(ticket.resolved_at)
                  : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {strings.tickets.detail.sla}
              </dt>
              <dd className="mt-0.5 text-slate-800">
                {ticket.sla ? (
                  <span className="block space-y-0.5">
                    <span className="block">
                      {strings.tickets.detail.target(
                        formatTargetMinutes(ticket.sla.target_minutes),
                      )}
                    </span>
                    <span className="block">
                      {strings.tickets.detail.due}:{' '}
                      {formatTicketDate(ticket.sla.due_at)}
                    </span>
                    <span className="block">
                      {strings.tickets.detail.remaining(
                        ticket.sla.remaining_minutes,
                      )}
                    </span>
                  </span>
                ) : (
                  strings.tickets.detail.noSla
                )}
              </dd>
            </div>
          </dl>

          <section aria-labelledby={`${fieldId}-description`}>
            <h3
              id={`${fieldId}-description`}
              className="text-sm font-semibold text-slate-900"
            >
              {strings.tickets.detail.description}
            </h3>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
              {ticket.description}
            </p>
          </section>

          {actionMessage ? (
            <p
              role="status"
              className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
            >
              {actionMessage}
            </p>
          ) : null}
          {actionError ? (
            <p
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {actionError}
            </p>
          ) : null}

          {canEdit ? (
            <fieldset
              disabled={closed || pending !== null}
              className="rounded-xl border border-slate-200 p-4"
            >
              <legend className="px-1 text-sm font-semibold text-slate-900">
                {strings.tickets.detail.actions}
              </legend>
              {closed ? (
                <p className="text-sm text-slate-600">
                  {strings.tickets.detail.closedNotice}
                </p>
              ) : null}

              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor={`${fieldId}-status`}
                    className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
                  >
                    {strings.tickets.detail.statusLabel}
                  </label>
                  {transitions.length > 0 ? (
                    <div className="mt-1 flex gap-2">
                      <select
                        id={`${fieldId}-status`}
                        value={status}
                        onChange={(event) => setStatus(event.target.value)}
                        className={SELECT_CLASS}
                      >
                        <option value={ticket.status}>{ticket.status}</option>
                        {transitions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => void handleStatus()}
                        disabled={pending !== null || status === ticket.status}
                        className={`${PRIMARY_BUTTON} whitespace-nowrap`}
                      >
                        {strings.tickets.detail.saveStatus}
                      </button>
                    </div>
                  ) : (
                    <p className="mt-1 text-sm text-slate-500">
                      {strings.tickets.detail.withoutTransitions}
                    </p>
                  )}
                </div>

                <div>
                  <label
                    htmlFor={`${fieldId}-priority`}
                    className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
                  >
                    {strings.tickets.detail.priorityLabel}
                  </label>
                  <div className="mt-1 flex gap-2">
                    <select
                      id={`${fieldId}-priority`}
                      value={priority}
                      onChange={(event) => setPriority(event.target.value)}
                      className={SELECT_CLASS}
                    >
                      {ticket.priority === null ? (
                        <option value="">{strings.tickets.noSla}</option>
                      ) : null}
                      {PRIORITIES.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => void handlePriority()}
                      disabled={
                        pending !== null ||
                        !priority ||
                        priority === (ticket.priority ?? '')
                      }
                      className={`${PRIMARY_BUTTON} whitespace-nowrap`}
                    >
                      {strings.tickets.detail.savePriority}
                    </button>
                  </div>
                </div>

                {canAssign ? (
                  <div className="sm:col-span-2">
                    <label
                      htmlFor={`${fieldId}-assignee`}
                      className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {strings.tickets.detail.assigneeLabel}
                    </label>
                    <div className="mt-1 flex gap-2">
                      <select
                        id={`${fieldId}-assignee`}
                        value={assignee}
                        onChange={(event) => setAssignee(event.target.value)}
                        className={SELECT_CLASS}
                      >
                        <option value="">{strings.tickets.unassigned}</option>
                        {(technicians.data ?? []).map((technician) => (
                          <option key={technician.id} value={technician.id}>
                            {technician.name}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => void handleAssignee()}
                        disabled={
                          pending !== null ||
                          !assignee ||
                          assignee === ticket.assignee?.id
                        }
                        className={`${PRIMARY_BUTTON} whitespace-nowrap`}
                      >
                        {strings.tickets.detail.saveAssignee}
                      </button>
                    </div>
                    {technicians.isSuccess && technicians.data.length === 0 ? (
                      <p className="mt-1 text-xs text-slate-500">
                        {strings.tickets.detail.noTechnicians}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </fieldset>
          ) : null}

          <section
            aria-labelledby={`${fieldId}-comments`}
            className="border-t border-slate-200 pt-4"
          >
            <h3
              id={`${fieldId}-comments`}
              className="text-sm font-semibold text-slate-900"
            >
              {strings.tickets.detail.comments}
            </h3>

            {comments.isPending ? (
              <Skeleton className="mt-2 h-16 w-full" />
            ) : comments.isError ? (
              <p role="alert" className="mt-2 text-sm text-red-700">
                {strings.tickets.detail.errorBody}
              </p>
            ) : comments.data.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">
                {strings.tickets.detail.noComments}
              </p>
            ) : (
              <ul className="mt-2 space-y-3">
                {comments.data.map((item) => (
                  <li
                    key={item.id}
                    className="rounded-xl border border-slate-200 bg-slate-50 p-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                      <span className="font-semibold text-slate-700">
                        {item.author?.name ?? '—'}
                      </span>
                      <span>{formatTicketDate(item.created_at)}</span>
                    </div>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
                      {item.body}
                    </p>
                  </li>
                ))}
              </ul>
            )}

            {canComment && !closed ? (
              <form noValidate onSubmit={handleComment} className="mt-3">
                <label
                  htmlFor={`${fieldId}-comment`}
                  className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
                >
                  {strings.tickets.detail.commentLabel}
                </label>
                <textarea
                  id={`${fieldId}-comment`}
                  value={comment}
                  rows={3}
                  maxLength={COMMENT_MAX_LENGTH + 1}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder={strings.tickets.detail.commentPlaceholder}
                  aria-invalid={Boolean(commentError)}
                  aria-describedby={
                    commentError ? `${fieldId}-comment-error` : undefined
                  }
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30 aria-[invalid=true]:border-red-500"
                />
                {commentError ? (
                  <p
                    id={`${fieldId}-comment-error`}
                    role="alert"
                    className="mt-1 text-sm text-red-700"
                  >
                    {commentError}
                  </p>
                ) : null}
                <button
                  type="submit"
                  disabled={commentPending}
                  className={`${PRIMARY_BUTTON} mt-2`}
                >
                  {commentPending
                    ? strings.tickets.detail.addingComment
                    : strings.tickets.detail.addComment}
                </button>
              </form>
            ) : null}
          </section>
        </div>
      )}
    </Modal>
  )
}
