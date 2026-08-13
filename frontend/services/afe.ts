import type { ApiClient } from '~/services/apiClient'
import type { EstimateAfeStatus } from '~/types/afe'

export class AfeApi {
  constructor(private readonly api: ApiClient) {}

  status(estimateId: string, versionId: string): Promise<EstimateAfeStatus> {
    return this.api.get(`/estimates/${estimateId}/afe?version_id=${versionId}`)
  }

  createBaseline(estimateId: string, versionId: string): Promise<EstimateAfeStatus> {
    return this.api.post(`/estimates/${estimateId}/afe/snapshots`, { version_id: versionId })
  }
}
