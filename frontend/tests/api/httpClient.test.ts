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

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
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

  it('conserva la notificación de un 401 vigente con señal activa', async () => {
    mockFetch(jsonResponse({ detail: 'sesión inválida' }, 401))
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    const controller = new AbortController()
    await expect(request('/api/test', { signal: controller.signal })).rejects.toMatchObject({
      status: 401, detail: 'sesión inválida',
    })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    expect(controller.signal.aborted).toBe(false)
  })

  it('no notifica un 401 recibido después de cancelar, pero conserva el rechazo HTTP', async () => {
    const response = deferred<Response>()
    const fetchMock = vi.fn<typeof fetch>(() => response.promise)
    vi.stubGlobal('fetch', fetchMock)
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    const controller = new AbortController()
    const pending = request('/api/test', { signal: controller.signal })
    controller.abort()
    // El doble ignora la cancelación para comprobar también la respuesta tardía.
    response.resolve(jsonResponse({ detail: 'sesión anterior' }, 401))
    await expect(pending).rejects.toMatchObject({ status: 401, detail: 'sesión anterior' })
    expect(fetchMock.mock.calls[0][1]?.signal).toBe(controller.signal)
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it.each(['detail', 'abort'])('no notifica 401 cancelado durante la lectura del cuerpo (%s)', async (result) => {
    const body = deferred<unknown>()
    const response = jsonResponse({}, 401)
    const readBody = vi.spyOn(response, 'json').mockImplementation(() => body.promise)
    mockFetch(response)
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    const controller = new AbortController()
    const pending = request('/api/test', { signal: controller.signal })
    // fetch se resuelve antes de cancelar: la petición ya está leyendo json().
    await Promise.resolve()
    expect(readBody).toHaveBeenCalledTimes(1)
    controller.abort()
    if (result === 'abort') body.reject(new DOMException('Aborted', 'AbortError'))
    else body.resolve({ detail: 'sesión anterior' })
    await expect(pending).rejects.toMatchObject({
      status: 401,
      detail: result === 'abort' ? 'Ocurrió un error inesperado' : 'sesión anterior',
    })
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it.each([404, 500])('conserva el error HTTP %i incluso con señal cancelada', async (status) => {
    mockFetch(jsonResponse({ detail: 'error original' }, status))
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    const controller = new AbortController()
    controller.abort()
    await expect(request('/api/test', { signal: controller.signal })).rejects.toMatchObject({
      status, detail: 'error original',
    })
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('propaga el AbortError de fetch sin notificar sesión expirada', async () => {
    const error = new DOMException('Aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(error))
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    const controller = new AbortController()
    controller.abort()
    await expect(request('/api/test', { signal: controller.signal })).rejects.toBe(error)
    expect(onUnauthorized).not.toHaveBeenCalled()
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
