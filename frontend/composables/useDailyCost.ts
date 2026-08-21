import { DailyCostApi } from '~/services/dailyCost'

export function useDailyCost(): DailyCostApi {
  return new DailyCostApi(useApi())
}
