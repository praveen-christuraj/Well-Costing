import type { ApiClient } from '~/services/apiClient'
import type { CostControlBatch, CostControlBatchPage, CostControlLineInput, CostState } from '~/types/costControl'

export class CostControlApi {
  constructor(private readonly api: ApiClient) {}
  list(): Promise<CostControlBatchPage> { return this.api.get('/cost-control/batches') }
  get(batchId: string): Promise<CostControlBatch> { return this.api.get(`/cost-control/batches/${batchId}`) }
  validate(estimateVersionId: string, costState: CostState, rows: CostControlLineInput[]): Promise<CostControlBatch> {
    return this.api.post('/cost-control/batches/validate', { estimate_version_id: estimateVersionId, cost_state: costState, rows })
  }
  post(batchId: string): Promise<CostControlBatch> { return this.api.post(`/cost-control/batches/${batchId}/post`, {}) }
  preview(estimateVersionId: string, costState: CostState, file: File): Promise<{ batch: CostControlBatch }> {
    const form = new FormData(); form.set('estimate_version_id', estimateVersionId); form.set('cost_state', costState); form.set('file', file)
    return this.api.postForm('/cost-control/imports/preview', form)
  }
  template(): Promise<Blob> { return this.api.download('/cost-control/template') }
}
