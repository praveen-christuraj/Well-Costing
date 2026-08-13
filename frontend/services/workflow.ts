import type { ApiClient } from '~/services/apiClient'
import type { EstimateWorkflowStatus, ReviewComment, WorkflowProfile } from '~/types/workflow'

export class WorkflowApi {
  constructor(private readonly api: ApiClient) {}

  profiles(): Promise<WorkflowProfile[]> {
    return this.api.get('/workflow/profiles')
  }

  status(estimateId: string, versionId: string): Promise<EstimateWorkflowStatus> {
    return this.api.get(`/estimates/${estimateId}/workflow?version_id=${versionId}`)
  }

  transition(estimateId: string, versionId: string, actionKey: string, comment: string | null): Promise<EstimateWorkflowStatus> {
    return this.api.post(`/estimates/${estimateId}/workflow/transitions`, {
      version_id: versionId,
      action_key: actionKey,
      comment,
    })
  }

  addComment(estimateId: string, versionId: string, body: string): Promise<ReviewComment> {
    return this.api.post(`/estimates/${estimateId}/review-comments`, { version_id: versionId, body })
  }
}
