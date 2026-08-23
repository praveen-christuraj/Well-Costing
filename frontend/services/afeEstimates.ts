import type { ApiClient } from '~/services/apiClient'
import type { AfeCostEstimate, AfeCostEstimateRateInput } from '~/types/afeEstimates'

/** AFE Cost Estimates: pricing the AFE lines with well-scoped unit rates. */
export class AfeEstimatesApi {
  constructor(private readonly api: ApiClient) {}

  get(afeId: string): Promise<AfeCostEstimate> {
    return this.api.get(`/afes/${afeId}/cost-estimate`)
  }

  saveRates(afeId: string, rates: AfeCostEstimateRateInput[]): Promise<AfeCostEstimate> {
    return this.api.put(`/afes/${afeId}/cost-estimate/rates`, { rates })
  }

  export(afeId: string): Promise<Blob> {
    return this.api.download(`/afes/${afeId}/cost-estimate/export`)
  }
}
