import type { ApiClient } from '~/services/apiClient'
import type { WellActivityRecord } from '~/types/dailyCost'

export interface WellActivityCreatePayload {
  well_id: string
  activity_id: string
  name: string
  responsible_party?: string | null
  description?: string | null
  is_active?: boolean
}

export interface WellActivityUpdatePayload {
  activity_id?: string
  name?: string
  responsible_party?: string | null
  description?: string | null
  is_active?: boolean
}

export class WellActivitiesApi {
  constructor(private readonly api: ApiClient) {}

  listForWell(wellId: string, includeInactive = false): Promise<WellActivityRecord[]> {
    const suffix = includeInactive ? '?include_inactive=true' : ''
    return this.api.get(`/well-activities/well/${wellId}${suffix}`)
  }

  create(payload: WellActivityCreatePayload): Promise<WellActivityRecord> {
    return this.api.post('/well-activities', payload as unknown as Record<string, unknown>)
  }

  update(id: string, payload: WellActivityUpdatePayload): Promise<WellActivityRecord> {
    return this.api.patch(`/well-activities/${id}`, payload as unknown as Record<string, unknown>)
  }

  remove(id: string): Promise<undefined> {
    return this.api.delete(`/well-activities/${id}`)
  }

  recover(id: string): Promise<WellActivityRecord> {
    return this.api.post(`/well-activities/${id}/recover`, {})
  }
}
