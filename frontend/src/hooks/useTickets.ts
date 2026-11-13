import { useQuery } from '@tanstack/react-query'

import { ticketsApi, type TicketsApi } from '@/api/tickets.api'
import type { TicketListScope } from '@/lib/tickets'
import type { TicketSummary } from '@/types/ticket'

export const ticketKeys = {
  lists: ['tickets', 'list'] as const,
  list: (scope: TicketListScope) => ['tickets', 'list', scope] as const,
  detail: (ticketId: string) => ['tickets', 'detail', ticketId] as const,
  comments: (ticketId: string) => ['tickets', 'comments', ticketId] as const,
  technicians: ['technicians'] as const,
}

function listRequest(
  scope: TicketListScope,
  api: TicketsApi,
): Promise<TicketSummary[]> {
  if (scope === 'all') return api.listAll()
  if (scope === 'assigned') return api.listAssigned()
  return api.listMine()
}

/** Listado de tickets del alcance indicado (`all`, `mine` o `assigned`). */
export function useTicketList(scope: TicketListScope, api: TicketsApi = ticketsApi) {
  return useQuery({
    queryKey: ticketKeys.list(scope),
    queryFn: () => listRequest(scope, api),
    retry: false,
  })
}

/** Detalle de un ticket; se desactiva mientras no haya identificador. */
export function useTicketDetail(
  ticketId: string | null,
  api: TicketsApi = ticketsApi,
) {
  return useQuery({
    queryKey: ticketKeys.detail(ticketId ?? 'none'),
    queryFn: () => api.getTicket(ticketId as string),
    enabled: Boolean(ticketId),
    retry: false,
  })
}

/** Comentarios de seguimiento del ticket abierto. */
export function useTicketComments(
  ticketId: string | null,
  api: TicketsApi = ticketsApi,
) {
  return useQuery({
    queryKey: ticketKeys.comments(ticketId ?? 'none'),
    queryFn: () => api.listComments(ticketId as string),
    enabled: Boolean(ticketId),
    retry: false,
  })
}

/** Directorio de técnicos; solo se consulta cuando el rol puede asignar. */
export function useTechnicians(api: TicketsApi = ticketsApi, enabled = true) {
  return useQuery({
    queryKey: ticketKeys.technicians,
    queryFn: () => api.listTechnicians(),
    enabled,
    retry: false,
  })
}
