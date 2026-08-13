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

export class NormalizedApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: unknown | null

  constructor(error: ApiErrorBody, status = 0) {
    super(error.message)
    this.name = 'NormalizedApiError'
    this.code = error.code
    this.status = status
    this.details = error.details
  }
}
