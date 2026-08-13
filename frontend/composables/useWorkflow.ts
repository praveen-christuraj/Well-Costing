import { WorkflowApi } from '~/services/workflow'

export function useWorkflow(): WorkflowApi {
  return new WorkflowApi(useApi())
}
