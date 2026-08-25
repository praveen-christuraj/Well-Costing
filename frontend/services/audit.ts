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

export interface AuditFilters {
  search?: string | undefined
  action?: string | undefined
  entity_type?: string | undefined
  actor_id?: string | undefined
}

function query(params: AuditFilters & { page?: number, page_size?: number }): string {
  const search = new URLSearchParams()
  if (params.page) search.set('page', String(params.page))
  if (params.page_size) search.set('page_size', String(params.page_size))
  if (params.search) search.set('search', params.search)
  if (params.action) search.set('action', params.action)
  if (params.entity_type) search.set('entity_type', params.entity_type)
  if (params.actor_id) search.set('actor_id', params.actor_id)
  return search.toString()
}

export class AuditApi {
  constructor(private readonly api: ApiClient) {}

  list(params: AuditFilters & { page?: number, page_size?: number } = {}): Promise<PageResponse<AuditLogRecord>> {
    return this.api.get(`/audit-logs?${query({ page: 1, page_size: 25, ...params })}`)
  }

  async listAll(filters: AuditFilters = {}): Promise<AuditLogRecord[]> {
    const first = await this.list({ ...filters, page: 1, page_size: 500 })
    const rows = [...first.items]
    for (let page = 2; page <= first.pages; page += 1) {
      const result = await this.list({ ...filters, page, page_size: 500 })
      rows.push(...result.items)
    }
    return rows
  }

  export(filters: AuditFilters = {}): Promise<Blob> {
    return this.api.download(`/audit-logs/export?${query(filters)}`)
  }

  get(id: string): Promise<AuditLogRecord> {
    return this.api.get(`/audit-logs/${id}`)
  }
}
