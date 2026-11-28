import type { SupportMetrics } from '@/types/supportMetrics'

export function buildSupportMetrics(
  overrides: Partial<SupportMetrics> = {},
): SupportMetrics {
  return {
    total_tickets: 3,
    resolved_tickets: 3,
    pending_tickets: 0,
    average_resolution_minutes: 120,
    resolution_sample_size: 3,
    resolution_excluded_count: 0,
    sla_compliance_percentage: 50,
    sla_sample_size: 2,
    sla_met_count: 1,
    sla_excluded_count: 1,
    ...overrides,
  }
}
