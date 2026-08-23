import { ReferenceApi } from '~/services/reference'

/** Client for the configurable dropdown registry. */
export function useReference(): ReferenceApi {
  return new ReferenceApi(useApi())
}
