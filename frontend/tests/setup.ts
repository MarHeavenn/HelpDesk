import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Vitest no corre con `globals: true`, así que el auto-cleanup de RTL no se registra.
afterEach(() => {
  cleanup()
  localStorage.clear()
})
