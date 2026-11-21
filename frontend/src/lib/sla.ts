import type { TicketSla } from '@/types/ticket'

export type SlaLevel = 'normal' | 'riesgo' | 'vencido' | 'sin_sla'

/**
 * Clasifica el SLA ya calculado por HU-05 en tres niveles visuales.
 * No recalcula fechas ni indica riesgo por su cuenta: solo interpreta
 * `breached`, `near_due` y `status` con precedencia de `breached`.
 */
export function slaLevel(sla: TicketSla | null): SlaLevel {
  if (!sla) return 'sin_sla'
  if (sla.breached) return 'vencido'
  if (sla.near_due) return 'riesgo'
  if (sla.status === 'incumplido') return 'vencido'
  if (sla.status === 'en_riesgo') return 'riesgo'
  return 'normal'
}
