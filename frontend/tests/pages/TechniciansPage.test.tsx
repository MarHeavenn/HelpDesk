import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'

import TechniciansPage from '@/pages/TechniciansPage'
import type { TechniciansApi } from '@/api/technicians.api'
import { renderApp } from '../helpers/renderApp'

describe('TechniciansPage', () => {
  it('muestra el directorio real de técnicos', async () => {
    const api: TechniciansApi = {
      list: vi.fn(async () => [
        { id: 'tech-1', name: 'Técnico Uno' },
        { id: 'tech-2', name: 'Técnica Dos' },
      ]),
    }
    renderApp(<TechniciansPage api={api} />)

    expect(await screen.findByText('Técnico Uno')).toBeInTheDocument()
    expect(screen.getByText('Técnica Dos')).toBeInTheDocument()
    expect(screen.getByText('Puedes asignar tickets desde el detalle de cada ticket.')).toBeInTheDocument()
  })

  it('muestra un estado vacío cuando no hay técnicos', async () => {
    const api: TechniciansApi = { list: vi.fn(async () => []) }
    renderApp(<TechniciansPage api={api} />)

    expect(await screen.findByText('No hay técnicos registrados')).toBeInTheDocument()
  })
})
