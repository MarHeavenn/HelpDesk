import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import TicketFilters from '@/components/tickets/TicketFilters'
import {
  DEFAULT_TICKET_FILTERS,
  clearTicketFilters,
  type TicketFilters as Filters,
} from '@/lib/tickets'

function Harness({ initial }: { initial?: Partial<Filters> }) {
  const [filters, setFilters] = useState<Filters>({
    ...DEFAULT_TICKET_FILTERS,
    ...initial,
  })

  return (
    <TicketFilters
      filters={filters}
      onChange={setFilters}
      technicians={[{ id: 'u-tech', name: 'Tomás Técnico' }]}
      showTechnician={false}
    />
  )
}

const SLA_LABELS = [
  'Todos',
  'Sin SLA',
  'En tiempo',
  'En riesgo',
  'Cumplido',
  'Incumplido',
]

describe('TicketFilters HU-17', () => {
  it('expone etiquetas accesibles y un campo libre de solicitante', () => {
    render(<Harness />)

    expect(screen.getByLabelText('Solicitante')).toHaveAttribute(
      'type',
      'search',
    )
    expect(
      screen.getByPlaceholderText('Buscar por nombre...'),
    ).toBe(screen.getByLabelText('Solicitante'))
    expect(screen.queryByLabelText('Técnico')).not.toBeInTheDocument()
  })

  it('ofrece seis opciones de SLA sin agrupar los estados', () => {
    render(<Harness initial={{ sla: 'none' }} />)

    const options = within(screen.getByLabelText('Estado del SLA')).getAllByRole(
      'option',
    )
    expect(options.map((option) => option.textContent)).toEqual(SLA_LABELS)
    expect(screen.getByLabelText('Estado del SLA')).toHaveValue('none')
  })

  it('aplica el solicitante tras el debounce y vuelve a la página 1', () => {
    vi.useFakeTimers()
    try {
      const onChange = vi.fn()
      render(
        <TicketFilters
          filters={{ ...DEFAULT_TICKET_FILTERS, page: 3 }}
          onChange={onChange}
          technicians={[]}
          showTechnician={false}
        />,
      )

      fireEvent.change(screen.getByLabelText('Solicitante'), {
        target: { value: '  María  ' },
      })
      act(() => vi.advanceTimersByTime(299))
      expect(onChange).not.toHaveBeenCalled()

      act(() => vi.advanceTimersByTime(1))
      expect(onChange).toHaveBeenCalledTimes(1)
      expect(onChange).toHaveBeenCalledWith({
        ...DEFAULT_TICKET_FILTERS,
        requester: 'María',
        page: 1,
      })
    } finally {
      vi.useRealTimers()
    }
  })

  it('cambia el SLA con teclado y guarda el criterio con página 1', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <TicketFilters
        filters={{ ...DEFAULT_TICKET_FILTERS, page: 4, sort: 'sla' }}
        onChange={onChange}
        technicians={[]}
        showTechnician={false}
      />,
    )

    await user.selectOptions(
      screen.getByLabelText('Estado del SLA'),
      'en_riesgo',
    )
    expect(onChange).toHaveBeenCalledWith({
      ...DEFAULT_TICKET_FILTERS,
      sla: 'en_riesgo',
      sort: 'sla',
      page: 1,
    })
  })

  it('limpia todo con una sola operación, conserva el orden y no reactiva el debounce', () => {
    vi.useFakeTimers()
    try {
      const dirty: Filters = {
        ...DEFAULT_TICKET_FILTERS,
        query: 'portal',
        requester: ' ana ',
        sla: 'none',
        status: 'Abierto',
        priority: 'Alta',
        sort: 'oldest',
        page: 2,
      }
      const calls: Filters[] = []

      function Controlled() {
        const [filters, setFilters] = useState<Filters>(dirty)
        return (
          <TicketFilters
            filters={filters}
            onChange={(next) => {
              calls.push(next)
              setFilters(next)
            }}
            technicians={[]}
            showTechnician={true}
          />
        )
      }

      render(<Controlled />)

      // Escritura pendiente del debounce justo antes de limpiar.
      fireEvent.change(screen.getByLabelText('Solicitante'), {
        target: { value: 'otra persona' },
      })
      fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }))

      expect(calls).toEqual([clearTicketFilters(dirty)])

      act(() => vi.advanceTimersByTime(300))
      expect(calls).toEqual([clearTicketFilters(dirty)])
    } finally {
      vi.useRealTimers()
    }
  })

  it('no reescribe el texto anterior si la limpieza llega desde fuera', () => {
    vi.useFakeTimers()
    try {
      const calls: Filters[] = []

      function ExternalCleanup() {
        const [filters, setFilters] = useState<Filters>({
          ...DEFAULT_TICKET_FILTERS,
          requester: 'ana',
        })
        return (
          <>
            <button
              type="button"
              onClick={() => setFilters(clearTicketFilters(filters))}
            >
              limpiar externo
            </button>
            <TicketFilters
              filters={filters}
              onChange={(next) => {
                calls.push(next)
                setFilters(next)
              }}
              technicians={[]}
              showTechnician={false}
            />
          </>
        )
      }

      render(<ExternalCleanup />)
      fireEvent.change(screen.getByLabelText('Solicitante'), {
        target: { value: 'otra persona' },
      })
      fireEvent.click(screen.getByRole('button', { name: 'limpiar externo' }))

      act(() => vi.advanceTimersByTime(300))
      expect(calls).toEqual([])
      expect(screen.getByLabelText('Solicitante')).toHaveValue('')
    } finally {
      vi.useRealTimers()
    }
  })

  it('sincroniza los controles al limpiar y deja el SLA en Todos', async () => {
    const user = userEvent.setup()
    render(
      <Harness
        initial={{
          query: 'portal',
          requester: 'ana',
          sla: 'none',
          status: 'Abierto',
          sort: 'sla',
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Limpiar filtros' }))

    expect(screen.getByLabelText('Buscar tickets')).toHaveValue('')
    expect(screen.getByLabelText('Solicitante')).toHaveValue('')
    expect(screen.getByLabelText('Estado del SLA')).toHaveValue('all')
    expect(screen.getByLabelText('Estado')).toHaveValue('all')
    expect(screen.getByLabelText('Ordenar por')).toHaveValue('sla')
    expect(
      screen.queryByRole('button', { name: 'Limpiar filtros' }),
    ).not.toBeInTheDocument()
  })
})
