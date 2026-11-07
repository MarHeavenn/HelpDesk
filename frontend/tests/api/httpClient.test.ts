import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  request,
  setUnauthorizedHandler,
} from '@/api/httpClient'

function mockFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  setUnauthorizedHandler(null)
})

describe('httpClient', () => {
  it('envía credenciales y devuelve el JSON de una respuesta correcta', async () => {
    const fetchMock = mockFetch(jsonResponse({ ok: true }))

    await expect(request('/api/test')).resolves.toEqual({ ok: true })

    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/test')
    expect(options).toMatchObject({
      method: 'GET',
      credentials: 'include',
    })
  })

  it('serializa el cuerpo y declara JSON en las peticiones con body', async () => {
    const fetchMock = mockFetch(jsonResponse({ id: 'u1' }, 201))

    await request('/api/auth/login', {
      method: 'POST',
      body: { email: 'ana@example.com', password: 'secreto' },
    })

    const [, options] = fetchMock.mock.calls[0]
    expect(options).toMatchObject({
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify({
        email: 'ana@example.com',
        password: 'secreto',
      }),
    })
    expect(options.headers).toEqual({ 'Content-Type': 'application/json' })
  })

  it('devuelve undefined en una respuesta 204', async () => {
    mockFetch(new Response(null, { status: 204 }))

    await expect(
      request<void>('/api/auth/logout', { method: 'POST' }),
    ).resolves.toBeUndefined()
  })

  it('lanza ApiError con el detalle de una respuesta 401 y avisa al manejador', async () => {
    mockFetch(jsonResponse({ detail: 'sesión inválida' }, 401))
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)

    await expect(request('/api/auth/me')).rejects.toMatchObject({
      status: 401,
      detail: 'sesión inválida',
    })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('normaliza un detalle de validación en lista', async () => {
    mockFetch(
      jsonResponse(
        {
          detail: [
            { msg: 'Field required', loc: ['body', 'email'] },
            { msg: 'Invalid email', loc: ['body', 'email'] },
          ],
        },
        422,
      ),
    )

    await expect(request('/api/tickets', { method: 'POST' })).rejects.toEqual(
      expect.objectContaining({
        status: 422,
        detail: 'Field required; Invalid email',
      }),
    )
  })

  it('usa un mensaje de respaldo cuando el error no trae JSON', async () => {
    mockFetch(new Response('boom', { status: 500 }))

    await expect(request('/api/test')).rejects.toBeInstanceOf(ApiError)
    await expect(request('/api/test')).rejects.toMatchObject({
      status: 500,
      detail: 'Ocurrió un error inesperado',
    })
  })
})
