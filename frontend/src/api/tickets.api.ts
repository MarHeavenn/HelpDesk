import { request } from '@/api/httpClient'

export interface TicketAssigneeDto {
  id: string
  name: string
}

export interface TicketSlaDto {
  target_minutes: number
  started_at: string
  due_at: string
  elapsed_minutes: number
  remaining_minutes: number
  status: string
  near_due: boolean
  breached: boolean
}

export interface TicketSummaryDto {
  id: string
  title: string
  priority: string | null
  status: string
  assignee: TicketAssigneeDto | null
  sla: TicketSlaDto | null
  created_at: string
}

export interface TicketRequesterDto {
  id: string
  name: string
  email: string
}

export interface TicketDto extends TicketSummaryDto {
  description: string
  requester: TicketRequesterDto | null
  resolved_at: string | null
  requester_id: string
}

export interface CreateTicketInput {
  title: string
  description: string
}

export interface CommentDto {
  id: string
  ticket_id: string
  body: string
  author: { id: string; name: string } | null
  created_at: string
}

export interface HistoryEventDto {
  action: string
  actor: { id: string; name: string | null }
  occurred_at: string
  previous_value: string | null
  new_value: string | null
  previous_assignee: { id: string; name: string | null } | null
  new_assignee: { id: string; name: string | null } | null
  comment: string | null
}

export function createTicketsApi(http: typeof request = request) {
  return {
    listMine(): Promise<TicketSummaryDto[]> {
      return http<TicketSummaryDto[]>('/api/tickets')
    },
    listAssigned(): Promise<TicketSummaryDto[]> {
      return http<TicketSummaryDto[]>('/api/assignments/mine')
    },
    create(input: CreateTicketInput): Promise<TicketDto> {
      return http<TicketDto>('/api/tickets', { method: 'POST', body: input })
    },
    get(id: string): Promise<TicketDto> {
      return http<TicketDto>(`/api/tickets/${id}`)
    },
    setPriority(id: string, priority: string): Promise<TicketDto> {
      return http<TicketDto>(`/api/tickets/${id}/priority`, {
        method: 'PUT',
        body: { priority },
      })
    },
    setStatus(id: string, status: string): Promise<TicketDto> {
      return http<TicketDto>(`/api/tickets/${id}/status`, {
        method: 'PUT',
        body: { status },
      })
    },
    reopen(id: string): Promise<TicketDto> {
      return http<TicketDto>(`/api/tickets/${id}/reopen`, { method: 'POST' })
    },
    assign(id: string, assigneeId: string): Promise<TicketDto> {
      return http<TicketDto>(`/api/tickets/${id}/assignee`, {
        method: 'PUT',
        body: { assignee_id: assigneeId },
      })
    },
    listComments(id: string): Promise<CommentDto[]> {
      return http<CommentDto[]>(`/api/tickets/${id}/comments`)
    },
    addComment(id: string, body: string): Promise<CommentDto> {
      return http<CommentDto>(`/api/tickets/${id}/comments`, {
        method: 'POST',
        body: { body },
      })
    },
    history(id: string): Promise<HistoryEventDto[]> {
      return http<HistoryEventDto[]>(`/api/tickets/${id}/history`)
    },
  }
}

export type TicketsApi = ReturnType<typeof createTicketsApi>

export const ticketsApi = createTicketsApi()
