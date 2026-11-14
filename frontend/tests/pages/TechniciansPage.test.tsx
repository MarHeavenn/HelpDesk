import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import TechniciansPage from '@/pages/TechniciansPage'
import type { TechniciansApi } from '@/api/technicians.api'

function renderPage(api: TechniciansApi) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <TechniciansPage api={api} />
    </QueryClientProvider>,
  )
}

describe('directorio de técnicos', () => {
  it('muestra el mensaje contractual cuando la API devuelve []', async () => {
    const api: TechniciansApi = {
      list: vi.fn(async () => []),
    }

    renderPage(api)

    expect(
      await screen.findByRole('heading', { name: 'Técnicos' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Aún no hay técnicos')).toBeInTheDocument()
    expect(api.list).toHaveBeenCalledOnce()
  })
})
