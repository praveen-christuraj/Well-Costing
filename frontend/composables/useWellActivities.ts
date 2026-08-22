import { ref } from 'vue'
import type { WellActivityRecord } from '~/types/dailyCost'

/**
 * Manage well-scoped sub-activities (Planned, NPT-1, NPT-2, UPA-1, etc.).
 */
export function useWellActivities() {
  const service = useWellActivitiesService()
  const wellActivities = ref<WellActivityRecord[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadForWell(wellId: string): Promise<void> {
    if (!wellId) {
      wellActivities.value = []
      return
    }
    loading.value = true
    error.value = null
    try {
      wellActivities.value = await service.listForWell(wellId)
    }
    catch (e: any) {
      error.value = e?.message || 'Failed to load well activities'
      wellActivities.value = []
    }
    finally {
      loading.value = false
    }
  }

  async function createActivity(payload: {
    well_id: string
    activity_id: string
    name: string
    responsible_party?: string | null
    description?: string | null
  }): Promise<WellActivityRecord | null> {
    error.value = null
    try {
      const record = await service.create(payload)
      wellActivities.value.push(record)
      return record
    }
    catch (e: any) {
      error.value = e?.message || 'Failed to create well activity'
      return null
    }
  }

  async function updateActivity(id: string, payload: {
    activity_id?: string
    name?: string
    responsible_party?: string | null
    description?: string | null
    is_active?: boolean
  }): Promise<WellActivityRecord | null> {
    error.value = null
    try {
      const record = await service.update(id, payload)
      const index = wellActivities.value.findIndex(a => a.id === id)
      if (index >= 0) {
        wellActivities.value[index] = record
      }
      return record
    }
    catch (e: any) {
      error.value = e?.message || 'Failed to update well activity'
      return null
    }
  }

  async function removeActivity(id: string): Promise<boolean> {
    error.value = null
    try {
      await service.remove(id)
      wellActivities.value = wellActivities.value.filter(a => a.id !== id)
      return true
    }
    catch (e: any) {
      error.value = e?.message || 'Failed to delete well activity'
      return false
    }
  }

  return {
    wellActivities,
    loading,
    error,
    loadForWell,
    createActivity,
    updateActivity,
    removeActivity,
  }
}
