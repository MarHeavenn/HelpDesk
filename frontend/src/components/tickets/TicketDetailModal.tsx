import { useEffect, useState } from 'react'

import { ApiError } from '@/api/httpClient'
import type { HistoryEventDto, TicketDto, TicketsApi } from '@/api/tickets.api'
import type { TechniciansApi } from '@/api/technicians.api'
import { PriorityBadge, StatusBadge } from '@/components/ui/Badges'
import type { Rol } from '@/types/domain'
import type { TicketView } from '@/lib/ticketMapper'
import { friendlyTicketId, mapTicket } from '@/lib/ticketMapper'
import { formatTicketDate } from '@/lib/dates'
import { strings } from '@/lib/strings'

const PRIORITIES = ['Crítica', 'Alta', 'Media', 'Baja']
const STATUSES = ['Abierto', 'En progreso', 'Resuelto', 'Cerrado']

export default function TicketDetailModal({
  ticket,
  role,
  api,
  techniciansApi,
  onClose,
  onUpdated,
}: {
  ticket: TicketView
  role: Rol
  api: TicketsApi
  techniciansApi: TechniciansApi
  onClose: () => void
  onUpdated: () => void
}) {
  const [detail, setDetail] = useState<TicketDto | null>(null)
  const [comments, setComments] = useState<Awaited<ReturnType<TicketsApi['listComments']>>>([])
  const [history, setHistory] = useState<HistoryEventDto[]>([])
  const [technicians, setTechnicians] = useState<Awaited<ReturnType<TechniciansApi['list']>>>([])
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  const current = detail ? mapTicket(detail) : ticket
  const canModify = role === 'administrador' || role === 'tecnico'
  const isAdmin = role === 'administrador'
  const isClosed = current.status === 'Cerrado'

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  useEffect(() => {
    let active = true
    async function load() {
      setIsLoading(true)
      setError(null)
      try {
        const [ticketDetail, ticketComments, ticketHistory] = await Promise.all([
          api.get(ticket.id),
          api.listComments(ticket.id),
          api.history(ticket.id),
        ])
        if (!active) return
        setDetail(ticketDetail)
        setComments(ticketComments)
        setHistory(ticketHistory)
        if (isAdmin) setTechnicians(await techniciansApi.list())
      } catch (cause) {
        if (active) setError(cause instanceof ApiError ? cause.detail : strings.tickets.detail.error)
      } finally {
        if (active) setIsLoading(false)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [api, isAdmin, techniciansApi, ticket.id])

  async function saveAction(action: () => Promise<TicketDto>) {
    setIsSaving(true)
    setError(null)
    try {
      const updated = await action()
      setDetail(updated)
      onUpdated()
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.detail : strings.tickets.detail.actionError)
    } finally {
      setIsSaving(false)
    }
  }

  async function addComment() {
    if (!comment.trim() || isClosed) return
    setIsSaving(true)
    setError(null)
    try {
      const created = await api.addComment(ticket.id, comment.trim())
      setComments((currentComments) => [...currentComments, created])
      setComment('')
      const refreshedHistory = await api.history(ticket.id)
      setHistory(refreshedHistory)
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.detail : strings.tickets.detail.commentError)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-slate-950/40 p-0 sm:items-center sm:p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="ticket-detail-title"
        className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl sm:p-7"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs text-slate-500">{friendlyTicketId(current.id)}</p>
            <h2 id="ticket-detail-title" className="mt-1 text-xl font-semibold text-slate-900">
              {current.title}
            </h2>
          </div>
          <button type="button" onClick={onClose} aria-label={strings.tickets.detail.close} className="rounded-lg px-2 py-1 text-xl text-slate-500 hover:bg-slate-100">
            ×
          </button>
        </div>

        {isLoading ? <p role="status" className="mt-6 text-sm text-slate-500">{strings.tickets.detail.loading}</p> : null}
        {error ? <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        {!isLoading ? (
          <div className="mt-6 space-y-6">
            <div className="flex flex-wrap items-center gap-2">
              <PriorityBadge priority={current.priority} />
              <StatusBadge status={current.status} />
              <span className="text-sm text-slate-500">{formatTicketDate(current.createdAt)}</span>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-800">{strings.tickets.detail.description}</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">{current.description ?? 'Descripción no disponible.'}</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{strings.tickets.detail.requester}</p>
                <p className="mt-1 text-sm text-slate-800">{current.requester?.name ?? 'No disponible'}</p>
              </div>
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{strings.tickets.detail.sla}</p>
                <p className="mt-1 text-sm text-slate-800">{current.sla?.status ?? strings.tickets.detail.noSla}</p>
              </div>
            </div>

            {canModify ? (
              <div className="grid gap-4 rounded-xl border border-slate-200 p-4 sm:grid-cols-3">
                <label className="text-sm font-semibold text-slate-700">
                  {strings.tickets.priority}
                  <select disabled={isClosed || isSaving} value={current.priority ?? ''} onChange={(event) => void saveAction(() => api.setPriority(current.id, event.target.value))} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2 py-2 font-normal">
                    <option value="">{strings.tickets.noPriority}</option>
                    {PRIORITIES.map((priority) => <option key={priority}>{priority}</option>)}
                  </select>
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  {strings.tickets.status}
                  <select disabled={isClosed || isSaving} value={current.status} onChange={(event) => void saveAction(() => api.setStatus(current.id, event.target.value))} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2 py-2 font-normal">
                    {STATUSES.map((status) => <option key={status}>{status}</option>)}
                  </select>
                </label>
                {isAdmin ? (
                  <label className="text-sm font-semibold text-slate-700">
                    {strings.tickets.detail.assign}
                    <select disabled={isClosed || isSaving} value={current.assignee?.id ?? ''} onChange={(event) => event.target.value && void saveAction(() => api.assign(current.id, event.target.value))} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2 py-2 font-normal">
                      <option value="">{strings.tickets.detail.unassigned}</option>
                      {technicians.map((technician) => <option key={technician.id} value={technician.id}>{technician.name}</option>)}
                    </select>
                  </label>
                ) : null}
              </div>
            ) : null}

            {isAdmin && isClosed ? <button type="button" disabled={isSaving} onClick={() => void saveAction(() => api.reopen(current.id))} className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white disabled:opacity-60">{strings.tickets.detail.reopen}</button> : null}

            <div>
              <h3 className="text-sm font-semibold text-slate-800">{strings.tickets.detail.comments}</h3>
              {comments.length === 0 ? <p className="mt-2 text-sm text-slate-500">{strings.tickets.detail.noComments}</p> : <div className="mt-2 space-y-2">{comments.map((item) => <article key={item.id} className="rounded-lg bg-slate-50 p-3"><p className="text-sm text-slate-700">{item.body}</p><p className="mt-1 text-xs text-slate-500">{item.author?.name ?? 'Usuario'} · {formatTicketDate(item.created_at)}</p></article>)}</div>}
              <div className="mt-3 flex gap-2">
                <input disabled={isClosed || isSaving} value={comment} onChange={(event) => setComment(event.target.value)} placeholder={strings.tickets.detail.commentPlaceholder} className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                <button type="button" disabled={isClosed || isSaving || !comment.trim()} onClick={() => void addComment()} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50">{strings.tickets.detail.addComment}</button>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-800">{strings.tickets.detail.history}</h3>
              {history.length === 0 ? <p className="mt-2 text-sm text-slate-500">{strings.tickets.detail.noHistory}</p> : <ol className="mt-2 space-y-2 border-l border-slate-200 pl-4">{history.map((item, index) => <li key={`${item.occurred_at}-${index}`} className="text-sm text-slate-600"><span className="font-semibold text-slate-800">{item.action}</span>{item.new_value ? ` · ${item.new_value}` : ''} <span className="text-xs text-slate-400">{formatTicketDate(item.occurred_at)}</span></li>)}</ol>}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  )
}
