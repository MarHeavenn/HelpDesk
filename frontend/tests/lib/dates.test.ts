import { describe, expect, it } from 'vitest'

import {
  formatLongDate,
  formatRelative,
  formatTicketDate,
  greetingForHour,
} from '@/lib/dates'

const TZ = 'America/Bogota'
const NOW = new Date('2026-06-19T15:30:00-05:00')

describe('formato de fechas es-CO', () => {
  it('formatea un ticket de hoy con la hora', () => {
    expect(
      formatTicketDate('2026-06-19T13:05:00-05:00', NOW, TZ),
    ).toBe('Hoy, 13:05')
  })

  it('formatea un ticket de ayer con la hora', () => {
    expect(
      formatTicketDate('2026-06-18T09:00:00-05:00', NOW, TZ),
    ).toBe('Ayer, 09:00')
  })

  it('formatea una fecha anterior con día y mes corto', () => {
    expect(
      formatTicketDate('2026-06-10T08:00:00-05:00', NOW, TZ),
    ).toBe('10 jun, 08:00')
  })

  it('devuelve un guion para una fecha inválida', () => {
    expect(formatTicketDate('no-es-fecha', NOW, TZ)).toBe('—')
  })

  it('formatea tiempos relativos', () => {
    expect(formatRelative('2026-06-19T15:22:00-05:00', NOW, TZ)).toBe(
      'Hace 8 min',
    )
    expect(formatRelative('2026-06-19T14:30:00-05:00', NOW, TZ)).toBe(
      'Hace 1 h',
    )
    expect(formatRelative('2026-06-18T10:00:00-05:00', NOW, TZ)).toBe('Ayer')
    expect(formatRelative('2026-06-05T10:00:00-05:00', NOW, TZ)).toBe('5 jun')
  })

  it('formatea la fecha larga en mayúsculas', () => {
    expect(formatLongDate('2026-06-19T12:00:00-05:00', TZ)).toBe(
      'VIERNES, 19 DE JUNIO',
    )
  })

  it('elige el saludo según la hora local', () => {
    expect(greetingForHour('2026-06-19T08:00:00-05:00', TZ)).toBe(
      'Buenos días',
    )
    expect(greetingForHour('2026-06-19T15:00:00-05:00', TZ)).toBe(
      'Buenas tardes',
    )
    expect(greetingForHour('2026-06-19T21:00:00-05:00', TZ)).toBe(
      'Buenas noches',
    )
  })
})
