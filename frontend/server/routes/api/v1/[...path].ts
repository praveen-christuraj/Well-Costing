import { createError, getRouterParam, proxyRequest, readRawBody } from 'h3'

/** Matches the Excel import 15 MB cap, with a little headroom for multipart framing. */
const MAX_UPLOAD_BYTES = 16 * 1024 * 1024

function isTimeout(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  return error.name === 'TimeoutError'
    || error.name === 'AbortError'
    || /timeout|aborted/i.test(error.message)
}

function apiError(statusCode: number, statusMessage: string, code: string, message: string) {
  return createError({
    statusCode,
    statusMessage,
    data: {
      error: {
        code,
        message,
        details: null,
      },
    },
  })
}

export default defineEventHandler(async (event) => {
  const path = getRouterParam(event, 'path') ?? ''
  const requestUrl = event.node.req.url ?? ''
  const queryIndex = requestUrl.indexOf('?')
  const query = queryIndex >= 0 ? requestUrl.slice(queryIndex) : ''

  const config = useRuntimeConfig(event)
  const base = config.apiInternalBase.replace(/\/$/, '')
  const target = `${base}/api/v1/${path}${query}`
  const timeoutMs = Number(config.apiProxyTimeoutMs)

  const method = event.node.req.method ?? 'GET'
  const hasBody = ['POST', 'PUT', 'PATCH'].includes(method.toUpperCase())

  if (hasBody) {
    const contentLength = Number(event.node.req.headers['content-length'] ?? 0)
    if (Number.isFinite(contentLength) && contentLength > MAX_UPLOAD_BYTES) {
      throw apiError(413, 'Payload Too Large', 'payload_too_large', 'Upload exceeds the 15 MB limit')
    }
    // Buffer as raw bytes. The default UTF-8 encoding corrupts Excel/multipart
    // uploads; proxyRequest then forwards a body whose length no longer matches
    // Content-Length and the API hangs or resets — the client sees 502.
    await readRawBody(event, false)
  }

  try {
    return await proxyRequest(event, target, {
      fetchOptions: { signal: AbortSignal.timeout(timeoutMs) },
    })
  }
  catch (error: unknown) {
    if (isTimeout(error)) {
      throw apiError(
        504,
        'Gateway Timeout',
        'gateway_timeout',
        'The API did not respond before the proxy timeout. Confirm the backend is running and try again.',
      )
    }
    const statusCode = typeof error === 'object' && error !== null && 'statusCode' in error
      ? Number((error as { statusCode?: number }).statusCode)
      : 0
    if (statusCode && statusCode !== 502) {
      throw error
    }
    throw apiError(
      502,
      'Bad Gateway',
      'bad_gateway',
      'The API could not be reached. Confirm the backend is running and try again.',
    )
  }
})
