import '@testing-library/jest-dom/vitest'

import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import App from '@/App'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('app', () => {
  it('monta el frontend y resuelve una sesión anónima contra la API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'sin sesión' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    render(<App />)

    expect(
      await screen.findByRole('heading', { name: 'No hay una sesión activa' }),
    ).toBeInTheDocument()
  })
})
