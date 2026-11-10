import { describe, expect, it, vi } from 'vitest'

import { createTechniciansApi } from '@/api/technicians.api'

describe('technicians.api', () => {
  it('consulta el directorio de técnicos', async () => {
    const http = vi.fn(async () => []) as unknown as Parameters<typeof createTechniciansApi>[0]

    await createTechniciansApi(http).list()

    expect(http).toHaveBeenCalledWith('/api/technicians')
  })
})
