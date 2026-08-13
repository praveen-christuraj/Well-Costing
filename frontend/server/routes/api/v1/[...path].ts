import { getRouterParam, proxyRequest } from 'h3'

export default defineEventHandler(async (event) => {
  const path = getRouterParam(event, 'path') ?? ''
  const requestUrl = event.node.req.url ?? ''
  const queryIndex = requestUrl.indexOf('?')
  const query = queryIndex >= 0 ? requestUrl.slice(queryIndex) : ''

  const config = useRuntimeConfig(event)
  const base = config.apiInternalBase.replace(/\/$/, '')
  const target = `${base}/api/v1/${path}${query}`
  const timeoutMs = Number(config.apiProxyTimeoutMs)

  return proxyRequest(event, target, {
    // Render Free services can take about a minute to wake after an idle spin-down.
    fetchOptions: { signal: AbortSignal.timeout(timeoutMs) },
  })
})
