import { AuditApi } from '~/services/audit'

export function useAudit(): AuditApi {
  return new AuditApi(useApi())
}
