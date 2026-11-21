import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import TicketTable from '@/components/tickets/TicketTable'
import { buildSla, buildSummary } from '../helpers/ticketFixtures'

function renderTable() {
  return render(
    <TicketTable
      tickets={[
        buildSummary({ id: 't-1', title: 'Dentro de plazo' }),
        buildSummary({
          id: 't-2',
          title: 'Ya vencido',
          sla: buildSla({
            status: 'en_riesgo',
            near_due: true,
            breached: true,
            remaining_minutes: 0,
          }),
        }),
        buildSummary({ id: 't-3', title: 'Sin prioridad', sla: null }),
      ]}
      caption="Listado de prueba"
      onOpen={vi.fn()}
    />,
  )
}

describe('TicketTable', () => {
  it('usa la misma señal de SLA en todas las filas', () => {
    const { container } = renderTable()

    const signals = container.querySelectorAll('[data-level]')
    expect(signals).toHaveLength(3)
    expect(Array.from(signals).map((item) => item.getAttribute('data-level'))).toEqual([
      'normal',
      'vencido',
      'sin_sla',
    ])

    const table = screen.getByRole('table', { name: 'Listado de prueba' })
    expect(within(table).getByText('En tiempo')).toBeInTheDocument()
    expect(within(table).getByText('Vencido')).toBeInTheDocument()
    expect(within(table).getByText('Sin SLA')).toBeInTheDocument()
    expect(within(table).getAllByText(/Vence:/)).toHaveLength(2)
  })
})
