export interface DashboardTechnician {
  id: string
  name: string
}

export interface StatusCount {
  status: string
  count: number
}

export interface PriorityCount {
  priority: string | null
  label: string
  count: number
}

export interface AssigneeCount {
  technician: DashboardTechnician | null
  label: string
  count: number
}

export interface RecentTicket {
  id: string
  title: string
  priority: string | null
  status: string
  assignee: DashboardTechnician | null
  created_at: string
}

/** Contrato de `GET /api/dashboard/tickets` (RF-84 a RF-90). */
export interface TicketDashboard {
  total_tickets: number
  by_status: StatusCount[]
  by_priority: PriorityCount[]
  by_assignee: AssigneeCount[]
  recent_tickets: RecentTicket[]
  generated_at: string
}
