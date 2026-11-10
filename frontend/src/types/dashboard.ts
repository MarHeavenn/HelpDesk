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

/** Desglose de cumplimiento por prioridad (RF-99). */
export interface SlaPriorityBreakdown {
  priority: string
  en_tiempo: number
  en_riesgo: number
  cumplido: number
  incumplido: number
  compliance_percentage: number
}

/** Contrato de `GET /api/dashboard/sla` (RF-98 a RF-101). */
export interface SlaDashboard {
  total_evaluated: number
  en_tiempo: number
  en_riesgo: number
  cumplido: number
  incumplido: number
  sin_sla: number
  compliance_percentage: number
  closed_without_resolved_at: number
  threshold_percent: number
  period_days: number
  by_priority: SlaPriorityBreakdown[]
  generated_at: string
}
