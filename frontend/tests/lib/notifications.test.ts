import { describe, expect, it } from 'vitest'

import { formatTicketDate } from '@/lib/dates'
import {
  notificationIcon,
  notificationMessage,
  notificationTypeLabel,
} from '@/lib/notifications'
import { buildNotification } from '../helpers/notificationFixtures'
import type { NotificationType } from '@/types/notification'

describe('lib/notifications', () => {
  it('describe la asignación y la reasignación con el técnico nuevo', () => {
    expect(
      notificationMessage(
        buildNotification({ new_value: 'Tomás Técnico' }),
      ),
    ).toBe('Ticket asignado a Tomás Técnico')
    expect(
      notificationMessage(
        buildNotification({
          type: 'ticket_reassigned',
          previous_value: 'Ana',
          new_value: 'Tomás Técnico',
        }),
      ),
    ).toBe('Ticket reasignado a Tomás Técnico')
  })

  it('describe el cambio de estado con los valores anterior y nuevo', () => {
    expect(
      notificationMessage(
        buildNotification({
          type: 'ticket_status_changed',
          previous_value: 'Abierto',
          new_value: 'En progreso',
        }),
      ),
    ).toBe('Estado actualizado: Abierto → En progreso')
  })

  it('describe resolución y reapertura', () => {
    expect(
      notificationMessage(buildNotification({ type: 'ticket_resolved' })),
    ).toBe('Ticket resuelto')
    expect(
      notificationMessage(buildNotification({ type: 'ticket_reopened' })),
    ).toBe('Ticket reabierto')
  })

  it('describe el SLA próximo a vencer y el incumplido con su fecha', () => {
    const due = '2026-11-17T13:00:00+00:00'
    const formatted = formatTicketDate(due)

    expect(
      notificationMessage(
        buildNotification({
          type: 'sla_near_due',
          new_value: due,
          actor: { id: 'system', name: 'Sistema' },
        }),
      ),
    ).toBe(`SLA por vencer: vence ${formatted}`)
    expect(
      notificationMessage(
        buildNotification({
          type: 'sla_breached',
          new_value: due,
          actor: { id: 'system', name: 'Sistema' },
        }),
      ),
    ).toBe(`SLA incumplido: venció ${formatted}`)
    expect(
      notificationMessage(
        buildNotification({ type: 'sla_breached', new_value: null }),
      ),
    ).toBe('SLA incumplido')
  })

  it('asigna un icono y una etiqueta a cada tipo', () => {
    const expected: Record<NotificationType, string> = {
      ticket_assigned: 'assigned',
      ticket_reassigned: 'reassigned',
      ticket_status_changed: 'status',
      ticket_resolved: 'resolved',
      ticket_reopened: 'reopened',
      sla_near_due: 'slaNearDue',
      sla_breached: 'slaBreached',
    }

    for (const [type, icon] of Object.entries(expected)) {
      expect(notificationIcon(type as NotificationType)).toBe(icon)
    }
    expect(notificationTypeLabel('ticket_resolved')).toBe('Resuelto')
    expect(notificationTypeLabel('sla_near_due')).toBe('SLA por vencer')
    expect(notificationTypeLabel('sla_breached')).toBe('SLA incumplido')
  })
})
