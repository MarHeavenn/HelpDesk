import { afterEach, describe, expect, it, vi } from 'vitest'

import { authApi } from '@/api/auth.api'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('auth.api', () => {
  it('inicia sesión con correo y contraseña', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: 'u1',
        name: 'Ana Torres',
        email: 'ana@example.com',
        role: 'tecnico',
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(authApi.login('ana@example.com', 'secreto')).resolves.toEqual({
      id: 'u1',
      name: 'Ana Torres',
      email: 'ana@example.com',
      role: 'tecnico',
    })

    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/auth/login')
    expect(options).toMatchObject({ method: 'POST' })
    expect(options.body).toBe(
      JSON.stringify({ email: 'ana@example.com', password: 'secreto' }),
    )
  })

  it('consulta la sesión y usa el correo como nombre de respaldo', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ id: 'u1', email: 'ana@example.com', role: 'tecnico' }),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(authApi.me()).resolves.toEqual({
      id: 'u1',
      name: 'ana@example.com',
      email: 'ana@example.com',
      role: 'tecnico',
    })
  })

  it('cierra la sesión con POST y acepta 204', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(authApi.logout()).resolves.toBeUndefined()

    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/auth/logout')
    expect(options).toMatchObject({ method: 'POST' })
  })
})
