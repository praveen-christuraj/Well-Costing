import { CostControlApi } from '~/services/costControl'
export function useCostControl(): CostControlApi { return new CostControlApi(useApi()) }
