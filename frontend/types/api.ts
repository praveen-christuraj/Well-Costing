export interface ApiErrorBody {
  code: string
  message: string
  details: unknown | null
}

export interface ApiError {
  error: ApiErrorBody
}

export interface ApiResponse<T> {
  data: T
}

function formatApiErrorMessage(error: ApiErrorBody): string {
  if (error.details && Array.isArray(error.details)) {
    const fields = error.details
      .map((detail: unknown) => {
        if (!detail || typeof detail !== 'object') return null
        const item = detail as { loc?: unknown[], msg?: unknown }
        const location = Array.isArray(item.loc) ? item.loc.slice(-1)[0] : null
        return item.msg ? `${location ? `${String(location)}: ` : ''}${String(item.msg)}` : null
      })
      .filter(Boolean)
    if (fields.length) return `${error.message}: ${fields.join('; ')}`
  }
  return error.message
}

export class NormalizedApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: unknown | null

  constructor(error: ApiErrorBody, status = 0) {
    super(formatApiErrorMessage(error))
    this.name = 'NormalizedApiError'
    this.code = error.code
    this.status = status
    this.details = error.details
  }
}
