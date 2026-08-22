import { useWellActivities } from '~/composables/useWellActivities'
import type { WellActivitiesApi } from '~/services/wellActivities'

describe('useWellActivities', () => {
  it('loads, creates, updates, and deletes activities for a well', async () => {
    const mockRecord = {
      id: 'wa-1',
      well_id: 'well-1',
      activity_id: 'act-1',
      name: 'Planned',
      responsible_party: null,
      description: null,
      is_active: true,
      created_at: '2026-08-22T00:00:00Z',
      updated_at: '2026-08-22T00:00:00Z',
    }
    const mockCreated = {
      id: 'wa-2',
      well_id: 'well-1',
      activity_id: 'act-2',
      name: 'NPT-1',
      responsible_party: 'Contractor',
      description: 'Breakdown',
      is_active: true,
      created_at: '2026-08-22T00:00:00Z',
      updated_at: '2026-08-22T00:00:00Z',
    }

    const listForWell = vi.fn().mockResolvedValue([mockRecord])
    const create = vi.fn().mockResolvedValue(mockCreated)
    const update = vi.fn().mockResolvedValue({ ...mockCreated, name: 'NPT-1 Revised' })
    const remove = vi.fn().mockResolvedValue(undefined)

    const mockApi = {
      listForWell,
      create,
      update,
      remove,
    } as unknown as WellActivitiesApi

    const composable = useWellActivities(mockApi)

    expect(composable.wellActivities.value).toEqual([])
    expect(composable.loading.value).toBe(false)
    expect(composable.error.value).toBeNull()

    // load
    await composable.loadForWell('well-1')
    expect(listForWell).toHaveBeenCalledWith('well-1')
    expect(composable.wellActivities.value).toEqual([mockRecord])
    expect(composable.loading.value).toBe(false)

    // create
    const created = await composable.createActivity({
      well_id: 'well-1',
      activity_id: 'act-2',
      name: 'NPT-1',
      responsible_party: 'Contractor',
    })
    expect(created).toEqual(mockCreated)
    expect(composable.wellActivities.value).toHaveLength(2)

    // update
    const updated = await composable.updateActivity('wa-2', { name: 'NPT-1 Revised' })
    expect(updated?.name).toBe('NPT-1 Revised')
    expect(composable.wellActivities.value.find(a => a.id === 'wa-2')?.name).toBe('NPT-1 Revised')

    // remove
    const deleted = await composable.removeActivity('wa-2')
    expect(deleted).toBe(true)
    expect(composable.wellActivities.value).toHaveLength(1)
  })

  it('handles empty wellId gracefully', async () => {
    const listForWell = vi.fn()
    const mockApi = { listForWell } as unknown as WellActivitiesApi
    const composable = useWellActivities(mockApi)

    await composable.loadForWell('')
    expect(listForWell).not.toHaveBeenCalled()
    expect(composable.wellActivities.value).toEqual([])
  })
})
