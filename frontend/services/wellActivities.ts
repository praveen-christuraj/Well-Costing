import type { WellActivityRecord } from '~/types/dailyCost'

interface WellActivityCreatePayload {
  well_id: string
  activity_id: string
  name: string
  responsible_party?: string | null
  description?: string | null
  is_active?: boolean
}

interface WellActivityUpdatePayload {
  activity_id?: string
  name?: string
  responsible_party?: string | null
  description?: string | null
  is_active?: boolean
}

export function useWellActivitiesService() {
  const { apiFetch } = useApi()

  async function listForWell(wellId: string): Promise<WellActivityRecord[]> {
    return apiFetch<WellActivityRecord[]>(`/well-activities/well/${wellId}`)
  }

  async function create(payload: WellActivityCreatePayload): Promise<WellActivityRecord> {
    return apiFetch<WellActivityRecord>('/well-activities', {
      method: 'POST',
      body: payload,
    })
  }

  async function update(id: string, payload: WellActivityUpdatePayload): Promise<WellActivityRecord> {
    return apiFetch<WellActivityRecord>(`/well-activities/${id}`, {
      method: 'PATCH',
      body: payload,
    })
  }

  async function remove(id: string): Promise<void> {
    await apiFetch<void>(`/well-activities/${id}`, { method: 'DELETE' })
  }

  return {
    listForWell,
    create,
    update,
    remove,
  }
}
