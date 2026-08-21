import type { ApiClient } from '~/services/apiClient'
import type { PageResponse } from '~/types/masterData'

export interface AuditLogRecord {
  id: string
  actor_id: string | null
  actor_email: string | null
  action: string
  entity_type: string
  entity_id: string | null
  entity_code: string | null
  details: string | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
  updated_at: string
}

export class AuditApi {
  constructor(private readonly api: ApiClient) {}

  list(params: Record<string, string | number | boolean | undefined> = {}): Promise<PageResponse<AuditLogRecord>> {
    const query = new URLSearchParams()
    query.set('page', String(params.page ?? 1))
    query.set('page_size', String(params.page_size ?? 25))
    if (params.search) query.set('search', String(params.search))
    if (params.action) query.set('action', String(params.action))
    if (params.entity_type) query.set('entity_type', String(params.entity_type))
    if (params.actor_id) query.set('actor_id', String(params.actor_id))
    return this.api.get(`/audit-logs?${query}`)
  }

  get(id: string): Promise<AuditLogRecord> {
    return this.api.get(`/audit-logs/${id}`)
  }
}
