import { AfeEstimatesApi } from '~/services/afeEstimates'

export function useAfeEstimates(): AfeEstimatesApi {
  return new AfeEstimatesApi(useApi())
}
