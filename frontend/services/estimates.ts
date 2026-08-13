import type { ApiClient } from '~/services/apiClient'
import type { CalculationResults } from '~/types/calculations'
import type { Estimate, EstimateItem, EstimateVersion } from '~/types/estimates'
import type { PageResponse } from '~/types/masterData'

export class EstimateApi {
  constructor(private readonly api: ApiClient) {}
  list(): Promise<PageResponse<Estimate>> { return this.api.get('/estimates?page=1&page_size=500') }
  get(id: string): Promise<Estimate> { return this.api.get(`/estimates/${id}`) }
  generate(payload: Record<string, unknown>): Promise<Estimate> { return this.api.post('/estimates/from-requirement', payload) }
  updateItems(rows: Record<string, unknown>[]): Promise<EstimateItem[]> { return this.api.patch('/estimates/items/bulk', { rows }) }
  assign(versionId: string, itemIds: string[], vendorId: string | null, rateId: string | null): Promise<EstimateItem[]> { return this.api.post(`/estimates/versions/${versionId}/bulk-assign`, { item_ids: itemIds, vendor_id: vendorId, rate_id: rateId }) }
  duplicateItems(versionId: string, itemIds: string[]): Promise<EstimateItem[]> { return this.api.post(`/estimates/versions/${versionId}/duplicate-items`, { item_ids: itemIds }) }
  assumption(versionId: string, payload: Record<string, unknown>): Promise<EstimateVersion> { return this.api.request(`/estimates/versions/${versionId}/assumptions`, { method: 'PUT', body: payload }) }
  duplicateVersion(estimateId: string, notes: string): Promise<EstimateVersion> { return this.api.post(`/estimates/${estimateId}/versions`, { notes }) }
  export(versionId: string): Promise<Blob> { return this.api.download(`/estimates/versions/${versionId}/export`) }
  template(versionId: string): Promise<Blob> { return this.api.download(`/estimates/versions/${versionId}/template`) }
  calculate(estimateId: string, versionId: string): Promise<CalculationResults> { return this.api.post(`/estimates/${estimateId}/calculate?version_id=${versionId}`, {}) }
  results(estimateId: string, versionId: string): Promise<CalculationResults> { return this.api.get(`/estimates/${estimateId}/results?version_id=${versionId}`) }
}
