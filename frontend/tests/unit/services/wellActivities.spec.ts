import type { ApiClient } from '~/services/apiClient'
import { WellActivitiesApi } from '~/services/wellActivities'

describe('WellActivitiesApi', () => {
  it('calls well activities endpoints with correct paths and payloads', async () => {
    const get = vi.fn().mockResolvedValue([{ id: 'wa-1', name: 'Planned' }])
    const post = vi.fn().mockResolvedValue({ id: 'wa-2', name: 'NPT-1' })
    const patch = vi.fn().mockResolvedValue({ id: 'wa-2', name: 'NPT-1 Updated' })
    const del = vi.fn().mockResolvedValue(undefined)
    const client = { get, post, patch, delete: del } as unknown as ApiClient
    const api = new WellActivitiesApi(client)

    const list = await api.listForWell('well-1')
    expect(get).toHaveBeenCalledWith('/well-activities/well/well-1')
    expect(list).toEqual([{ id: 'wa-1', name: 'Planned' }])

    const created = await api.create({
      well_id: 'well-1',
      activity_id: 'act-1',
      name: 'NPT-1',
      responsible_party: 'Rig Contractor',
      description: 'Top drive failure',
    })
    expect(post).toHaveBeenCalledWith('/well-activities', {
      well_id: 'well-1',
      activity_id: 'act-1',
      name: 'NPT-1',
      responsible_party: 'Rig Contractor',
      description: 'Top drive failure',
    })
    expect(created.id).toBe('wa-2')

    const updated = await api.update('wa-2', {
      name: 'NPT-1 Updated',
      responsible_party: 'Operator',
    })
    expect(patch).toHaveBeenCalledWith('/well-activities/wa-2', {
      name: 'NPT-1 Updated',
      responsible_party: 'Operator',
    })
    expect(updated.name).toBe('NPT-1 Updated')

    await api.remove('wa-2')
    expect(del).toHaveBeenCalledWith('/well-activities/wa-2')
  })
})
