import { WellCostingApi } from '~/services/wellCosting'

export function useWellCosting(): WellCostingApi {
  return new WellCostingApi(useApi())
}
