import { $fetch, FetchError, type FetchOptions, type $Fetch } from 'ofetch'
import { NormalizedApiError, type ApiError, type ApiErrorBody } from '~/types/api'

export type AccessTokenProvider = () => string | null

function isApiError(value: unknown): value is ApiError {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const candidate = (value as { error?: unknown }).error
  return (
    typeof candidate === 'object'
    && candidate !== null
    && 'code' in candidate
    && 'message' in candidate
  )
}

/** FastAPI validation errors are returned as { detail: [...] }, while our
 * application errors use { error: ... }. Keep the field-level reason visible
 * to the form instead of reducing every bad AFE payload to "network error". */
function validationErrorBody(value: unknown): ApiErrorBody | null {
  if (typeof value !== 'object' || value === null || !('detail' in value)) return null
  const detail = (value as { detail?: unknown }).detail
  return { code: 'validation_error', message: 'Please correct the highlighted data', details: Array.isArray(detail) ? detail : [{ msg: String(detail) }] }
}

export class ApiClient {
  private readonly client: $Fetch

  constructor(
    private readonly baseURL: string,
    private readonly getAccessToken: AccessTokenProvider = () => null,
  ) {
    this.client = $fetch.create({
      baseURL,
      onRequest: ({ options }) => this.applyAuthorization(options),
    })
  }

  async request<T>(path: string, options: FetchOptions<'json'> = {}): Promise<T> {
    try {
      return await this.client<T>(path, options)
    }
    catch (error: unknown) {
      this.raiseNormalized(error)
    }
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'GET' })
  }

  post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return this.request<T>(path, { method: 'POST', body })
  }

  postForm<T>(path: string, body: FormData): Promise<T> {
    return this.request<T>(path, { method: 'POST', body })
  }

  patch<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return this.request<T>(path, { method: 'PATCH', body })
  }

  put<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return this.request<T>(path, { method: 'PUT', body })
  }

  delete(path: string): Promise<undefined> {
    return this.request<undefined>(path, { method: 'DELETE' })
  }

  /** DELETE that returns a body, e.g. resetting a dropdown binding. */
  deleteJson<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' })
  }

  async download(path: string): Promise<Blob> {
    const headers = new Headers()
    const token = this.getAccessToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(`${this.baseURL.replace(/\/$/, '')}/${path.replace(/^\//, '')}`, {
      headers,
    })
    if (!response.ok) {
      let body: unknown
      try { body = await response.json() }
      catch { body = null }
      if (isApiError(body)) throw new NormalizedApiError(body.error, response.status)
      throw new NormalizedApiError({
        code: 'download_failed',
        message: `Download failed with status ${response.status}`,
        details: body,
      }, response.status)
    }
    return response.blob()
  }

  private applyAuthorization(options: FetchOptions): void {
    const token = this.getAccessToken()
    if (token) {
      const headers = new Headers(options.headers)
      headers.set('Authorization', `Bearer ${token}`)
      options.headers = headers
    }
  }

  private raiseNormalized(error: unknown): never {
    if (error instanceof FetchError) {
      if (isApiError(error.data)) {
        throw new NormalizedApiError(error.data.error, error.statusCode ?? 0)
      }
      const validation = validationErrorBody(error.data)
      if (validation) throw new NormalizedApiError(validation, error.statusCode ?? 0)
      throw new NormalizedApiError(
        {
          code: 'network_error',
          message: error.message || 'The API request failed',
          details: error.data ?? null,
        },
        error.statusCode ?? 0,
      )
    }
    throw new NormalizedApiError({
      code: 'unknown_error',
      message: error instanceof Error ? error.message : 'An unknown error occurred',
      details: null,
    })
  }
}
