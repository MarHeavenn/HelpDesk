const API_URL = (
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
).replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

/** Registra el cierre de sesión que se dispara ante un 401 global. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

function normalizeDetail(payload: unknown): string {
  if (typeof payload === 'string' && payload.trim()) return payload

  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (item && typeof item === 'object' && 'msg' in item) {
            const message = (item as { msg: unknown }).msg
            return typeof message === 'string' ? message : ''
          }
          return ''
        })
        .filter((message) => message.length > 0)
      if (messages.length > 0) return messages.join('; ')
    }
  }

  return 'Ocurrió un error inesperado'
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    return normalizeDetail(await response.json())
  } catch {
    return 'Ocurrió un error inesperado'
  }
}

/** Cliente HTTP único: cookie de sesión, JSON y errores tipados. */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const hasBody = options.body !== undefined

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? 'GET',
    credentials: 'include',
    headers: hasBody ? { 'Content-Type': 'application/json' } : undefined,
    body: hasBody ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })

  if (!response.ok) {
    const detail = await readErrorDetail(response)
    if (response.status === 401) unauthorizedHandler?.()
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204 || response.status === 205) {
    return undefined as T
  }

  const text = await response.text()
  if (!text) return undefined as T

  try {
    return JSON.parse(text) as T
  } catch {
    throw new ApiError(response.status, 'Respuesta inválida del servidor')
  }
}
