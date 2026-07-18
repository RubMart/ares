export class ApiError extends Error {
  status: number
  payload: unknown

  constructor(status: number, payload: unknown) {
    super(formatDetail(payload) || `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

function formatDetail(payload: unknown): string | null {
  if (!payload) return null
  if (typeof payload === 'string') return payload
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === 'object' && item !== null && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : JSON.stringify(item),
        )
        .join('; ')
    }
    return JSON.stringify(detail)
  }
  return JSON.stringify(payload)
}

export function getApiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_URL?.trim()
  if (!base) {
    throw new ApiError(0, {
      detail: 'NEXT_PUBLIC_API_URL no está configurada',
    })
  }
  return base.replace(/\/+$/, '')
}

const DEFAULT_TIMEOUT_MS = 12_000

export type ApiRequestOptions = {
  signal?: AbortSignal
  timeoutMs?: number
}

/** @deprecated Prefer ApiRequestOptions */
export type ApiGetOptions = ApiRequestOptions

async function apiFetch<T>(
  path: string,
  init: RequestInit,
  options: ApiRequestOptions = {},
): Promise<T> {
  const url = `${getApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const controller = new AbortController()
  const onAbort = () => controller.abort()
  options.signal?.addEventListener('abort', onAbort)

  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  let response: Response

  try {
    response = await fetch(url, { ...init, signal: controller.signal })
  } catch (error) {
    if (options.signal?.aborted) {
      throw error instanceof Error ? error : new DOMException('Aborted', 'AbortError')
    }
    if (controller.signal.aborted) {
      throw new ApiError(0, {
        detail: `La API no respondió a tiempo (${timeoutMs / 1000}s). ¿Está uvicorn en marcha?`,
      })
    }
    const message = error instanceof Error ? error.message : String(error)
    throw new ApiError(0, {
      detail: `No se pudo conectar con la API (${message})`,
    })
  } finally {
    clearTimeout(timeoutId)
    options.signal?.removeEventListener('abort', onAbort)
  }

  let payload: unknown = null
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    payload = await response.json()
  } else if (!response.ok) {
    payload = { detail: await response.text() }
  }

  if (!response.ok) {
    throw new ApiError(response.status, payload)
  }

  return payload as T
}

export async function apiGet<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  return apiFetch<T>(path, {}, options)
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  options: ApiRequestOptions = {},
): Promise<T> {
  return apiFetch<T>(
    path,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
    },
    options,
  )
}
