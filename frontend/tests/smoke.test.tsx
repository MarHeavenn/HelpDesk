import '@testing-library/jest-dom/vitest'

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from '@/App'

describe('scaffold del frontend', () => {
  it('renderiza el título de la aplicación', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'Estructura del frontend' }),
    ).toBeInTheDocument()
  })
})
