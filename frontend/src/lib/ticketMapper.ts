import type { TicketDto, TicketSummaryDto } from '@/api/tickets.api'

export interface TicketView {
  id: string
  displayId: string
  title: string
  description?: string
  priority: string | null
  status: string
  assignee: { id: string; name: string } | null
  requester?: { id: string; name: string; email: string } | null
  createdAt: string
  resolvedAt?: string | null
  sla: TicketDto['sla']
}

export function friendlyTicketId(id: string): string {
  return `TCK-${id.replace(/-/g, '').slice(0, 6).toUpperCase()}`
}

export function mapTicket(ticket: TicketSummaryDto | TicketDto): TicketView {
  return {
    id: ticket.id,
    displayId: friendlyTicketId(ticket.id),
    title: ticket.title,
    description: 'description' in ticket ? ticket.description : undefined,
    priority: ticket.priority,
    status: ticket.status,
    assignee: ticket.assignee,
    requester: 'requester' in ticket ? ticket.requester : undefined,
    createdAt: ticket.created_at,
    resolvedAt: 'resolved_at' in ticket ? ticket.resolved_at : undefined,
    sla: ticket.sla,
  }
}
