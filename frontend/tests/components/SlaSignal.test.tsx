import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import SlaSignal from '@/components/ui/SlaSignal'
import { slaLevel } from '@/lib/sla'
import type { TicketSla } from '@/types/ticket'

function sla(overrides: Partial<TicketSla> = {}): TicketSla {
  return {
    target_minutes: 240,
    started_at: '2026-11-21T08:00:00+00:00',
    due_at: '2026-11-21T12:00:00+00:00',
    elapsed_minutes: 60,
    remaining_minutes: 180,
    status: 'en_tiempo',
    near_due: false,
    breached: false,
    ...overrides,
  }
}

describe('SlaSignal', () => {
  it('muestra el estado normal con su etiqueta de HU-05', () => {
    const { container } = render(<SlaSignal sla={sla()} />)

    expect(screen.getByText('En tiempo')).toBeInTheDocument()
    expect(container.firstChild).toHaveAttribute('data-level', 'normal')
    expect(slaLevel(sla())).toBe('normal')
  })

  it('muestra los tickets cumplidos como estado normal', () => {
    const { container } = render(
      <SlaSignal sla={sla({ status: 'cumplido' })} />,
    )

    expect(screen.getByText('Cumplido')).toBeInTheDocument()
    expect(container.firstChild).toHaveAttribute('data-level', 'normal')
  })

  it('señala como próximo a vencer cuando near_due es verdadero', () => {
    const { container } = render(
      <SlaSignal sla={sla({ status: 'en_riesgo', near_due: true })} />,
    )

    expect(screen.getByText('Próximo a vencer')).toBeInTheDocument()
    expect(container.firstChild).toHaveAttribute('data-level', 'riesgo')
  })

  it('da precedencia a breached sobre near_due y sobre status', () => {
    const { container } = render(
      <SlaSignal
        sla={sla({
          status: 'en_riesgo',
          near_due: true,
          breached: true,
          remaining_minutes: 0,
        })}
      />,
    )

    expect(screen.getByText('Vencido')).toBeInTheDocument()
    expect(container.firstChild).toHaveAttribute('data-level', 'vencido')
    expect(slaLevel(sla({ breached: true, near_due: true }))).toBe('vencido')
  })

  it('clasifica incumplido sin indicadores como vencido', () => {
    expect(slaLevel(sla({ status: 'incumplido' }))).toBe('vencido')
  })

  it('muestra Sin SLA sin tono de incidente cuando no hay prioridad', () => {
    const { container } = render(<SlaSignal sla={null} />)

    expect(screen.getByText('Sin SLA')).toBeInTheDocument()
    expect(container.firstChild).toHaveAttribute('data-level', 'sin_sla')
    expect(slaLevel(null)).toBe('sin_sla')
  })

  it('anuncia el nivel por texto e icono, no solo por color', () => {
    const { container } = render(
      <SlaSignal sla={sla({ status: 'en_riesgo', near_due: true })} />,
    )

    expect(screen.getByText('Próximo a vencer')).toBeVisible()
    expect(container.querySelector('svg')).toBeInTheDocument()
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })
})
