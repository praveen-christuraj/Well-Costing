import { EstimateApi } from '~/services/estimates'
export function useEstimates(): EstimateApi { return new EstimateApi(useApi()) }
