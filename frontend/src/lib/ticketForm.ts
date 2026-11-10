import { strings } from '@/lib/strings'

/** Límites de HU-02: 1–200 y 1–5000 caracteres tras recortar. */
export const TITLE_MAX_LENGTH = 200
export const DESCRIPTION_MAX_LENGTH = 5000

export interface TicketFieldErrors {
  title?: string
  description?: string
}

/** Longitud en code points, igual que `len()` de Python sobre `str`. */
export function codePointLength(value: string): number {
  return Array.from(value).length
}

/** Valida título y descripción ya alineados con el contrato de creación. */
export function validateTicketFields(
  title: string,
  description: string,
): TicketFieldErrors {
  const errors: TicketFieldErrors = {}
  const normalizedTitle = title.trim()
  const normalizedDescription = description.trim()

  if (!normalizedTitle) {
    errors.title = strings.createTicket.titleRequired
  } else if (codePointLength(normalizedTitle) > TITLE_MAX_LENGTH) {
    errors.title = strings.createTicket.titleTooLong
  }

  if (!normalizedDescription) {
    errors.description = strings.createTicket.descriptionRequired
  } else if (codePointLength(normalizedDescription) > DESCRIPTION_MAX_LENGTH) {
    errors.description = strings.createTicket.descriptionTooLong
  }

  return errors
}

/** Horas de SLA tal como las expone GET /api/sla/policies. */
export function formatTargetHours(hours: number): string {
  const amount = Number.isInteger(hours) ? String(hours) : String(hours)
  return hours === 1 ? `${amount} hora` : `${amount} horas`
}
