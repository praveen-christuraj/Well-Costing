import { EnterpriseConfigApi } from '~/services/enterpriseConfig'
export function useEnterpriseConfig(): EnterpriseConfigApi { return new EnterpriseConfigApi(useApi()) }
