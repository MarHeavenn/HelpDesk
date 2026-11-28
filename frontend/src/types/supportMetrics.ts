/** Agregado HU-18 calculado por el backend, sin tickets individuales. */
export interface SupportMetrics {
  total_tickets: number
  resolved_tickets: number
  pending_tickets: number
  average_resolution_minutes: number | null
  resolution_sample_size: number
  resolution_excluded_count: number
  sla_compliance_percentage: number | null
  sla_sample_size: number
  sla_met_count: number
  sla_excluded_count: number
}
