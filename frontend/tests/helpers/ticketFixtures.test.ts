import { describe, expect, it } from 'vitest'

import { buildAttentionTickets, buildTicketDashboard } from './dashboardFixtures'
import { buildSummary, buildTicket } from './ticketFixtures'

describe('fixtures del resumen aditivo (HU-17 T3)', () => {
  it('representa el resumen actual con solo el nombre del solicitante', () => {
    const summary = buildSummary()

    expect(summary.requester).toEqual({ name: 'Carla Cliente' })
    expect(Object.keys(summary).sort()).toEqual(
      ['id', 'title', 'priority', 'status', 'assignee', 'sla', 'created_at', 'requester'].sort(),
    )
  })

  it('permite un solicitante no resoluble y un resumen anterior sin campo', () => {
    expect(buildSummary({ requester: null }).requester).toBeNull()
    const legacy = buildSummary()
    delete legacy.requester
    expect(legacy).not.toHaveProperty('requester')
  })

  it('actualiza únicamente los resúmenes de atención, no los agregados ni el detalle', () => {
    const attention = buildAttentionTickets()
    expect(attention[0].requester).toEqual({ name: 'Carla Cliente' })
    expect(attention[1].requester).toBeNull()
    expect(buildTicket().requester).toEqual({
      id: 'u-client',
      name: 'Carla Cliente',
      email: 'carla@example.com',
    })
    for (const recent of buildTicketDashboard().recent_tickets) {
      expect(recent).not.toHaveProperty('requester')
    }
  })
})
