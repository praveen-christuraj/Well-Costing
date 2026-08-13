import { RequirementApi } from '~/services/requirements'

export function useRequirements(): RequirementApi {
  return new RequirementApi(useApi())
}
