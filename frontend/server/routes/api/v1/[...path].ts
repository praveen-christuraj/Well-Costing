import { getRouterParam, readRawBody, proxyRequest } from 'h3'

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
    // Read the raw body so h3 buffers it before proxying — avoids stream-drain issues
    await readRawBody(event)
  }

  return proxyRequest(event, target, {
    fetchOptions: { signal: AbortSignal.timeout(timeoutMs) },
  })
})
