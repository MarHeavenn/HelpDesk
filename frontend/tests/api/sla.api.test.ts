import { describe, expect, it, vi } from 'vitest'

import { createSlaApi, type SlaPolicies } from '@/api/sla.api'

describe('sla.api', () => {
  it('consulta y reemplaza las políticas reales', async () => {
    const http = vi.fn(async () => []) as unknown as Parameters<typeof createSlaApi>[0]
    const api = createSlaApi(http)
    const policies: SlaPolicies = { Crítica: 2, Alta: 4, Media: 12, Baja: 24 }

    await api.list()
    await api.replace(policies)

    expect(http).toHaveBeenNthCalledWith(1, '/api/sla/policies')
    expect(http).toHaveBeenNthCalledWith(2, '/api/sla/policies', { method: 'PUT', body: policies })
  })
})
