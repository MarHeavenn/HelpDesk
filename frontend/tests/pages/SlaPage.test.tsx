import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import SlaPage from '@/pages/SlaPage'
import type { SlaApi, SlaPolicies } from '@/api/sla.api'
import { renderApp } from '../helpers/renderApp'

const initial = [
  { priority: 'Crítica', hours: 2 },
  { priority: 'Alta', hours: 4 },
  { priority: 'Media', hours: 12 },
  { priority: 'Baja', hours: 24 },
]

describe('SlaPage', () => {
  it('carga y guarda políticas SLA reales', async () => {
    const api: SlaApi = {
      list: vi.fn(async () => initial),
      replace: vi.fn(async (policies: SlaPolicies) => Object.entries(policies).map(([priority, hours]) => ({ priority, hours: Number(hours) }))),
    }
    const user = userEvent.setup()
    renderApp(<SlaPage api={api} />)

    const media = await screen.findByLabelText('Media')
    await user.clear(media)
    await user.type(media, '10')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() => expect(api.replace).toHaveBeenCalledWith({ Crítica: 2, Alta: 4, Media: 10, Baja: 24 }))
  })

  it('rechaza valores no positivos', async () => {
    const api: SlaApi = { list: vi.fn(async () => initial), replace: vi.fn() }
    const user = userEvent.setup()
    renderApp(<SlaPage api={api} />)

    const alta = await screen.findByLabelText('Alta')
    await user.clear(alta)
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(await screen.findByText('Todas las prioridades deben tener un valor mayor que cero.')).toBeInTheDocument()
    expect(api.replace).not.toHaveBeenCalled()
  })
})
