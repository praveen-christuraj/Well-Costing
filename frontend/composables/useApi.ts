import { ApiClient } from '~/services/apiClient'

export function useApi(): ApiClient {
  const config = useRuntimeConfig()
  const accessToken = useAccessTokenCookie()
  return new ApiClient(config.public.apiBase, () => accessToken.value)
}
