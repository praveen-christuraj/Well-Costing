import { AfeApi } from '~/services/afe'

export function useAfe(): AfeApi {
  return new AfeApi(useApi())
}
