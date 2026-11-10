import { useLocation } from 'react-router-dom'

import { strings } from '@/lib/strings'

/**
 * Aviso de alta correcta al volver a Mis tickets, incluida la advertencia de
 * que la prioridad no se pudo persistir (RF-55).
 */
export default function CreatedTicketNotice() {
  const location = useLocation()
  const state = location.state as
    | { createdTicketId?: unknown; priorityError?: unknown }
    | null
  const createdTicketId = state?.createdTicketId
  const priorityError = state?.priorityError

  if (typeof createdTicketId !== 'string' || !createdTicketId) return null

  return (
    <div className="mb-4 space-y-2">
      <p
        role="status"
        className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
      >
        {strings.createTicket.created(createdTicketId)}
      </p>
      {typeof priorityError === 'string' && priorityError ? (
        <p
          role="alert"
          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
        >
          {strings.createTicket.priorityFailed(createdTicketId, priorityError)}
        </p>
      ) : null}
    </div>
  )
}
