import { ref } from 'vue'
import { WellActivitiesApi } from '~/services/wellActivities'
import type { WellActivityCreatePayload, WellActivityUpdatePayload } from '~/services/wellActivities'
import type { WellActivityRecord } from '~/types/dailyCost'

/**
 * Manage well-scoped sub-activities (Planned, NPT-1, NPT-2, UPA-1, etc.).
 */
export function useWellActivities(api: WellActivitiesApi = new WellActivitiesApi(useApi())) {
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
      wellActivities.value = await api.listForWell(wellId)
    }
    catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load well activities'
      wellActivities.value = []
    }
    finally {
      loading.value = false
    }
  }

  async function createActivity(payload: WellActivityCreatePayload): Promise<WellActivityRecord | null> {
    error.value = null
    try {
      const record = await api.create(payload)
      wellActivities.value.push(record)
      return record
    }
    catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to create well activity'
      return null
    }
  }

  async function updateActivity(id: string, payload: WellActivityUpdatePayload): Promise<WellActivityRecord | null> {
    error.value = null
    try {
      const record = await api.update(id, payload)
      const index = wellActivities.value.findIndex(a => a.id === id)
      if (index >= 0) {
        wellActivities.value[index] = record
      }
      return record
    }
    catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to update well activity'
      return null
    }
  }

  async function removeActivity(id: string): Promise<boolean> {
    error.value = null
    try {
      await api.remove(id)
      wellActivities.value = wellActivities.value.filter(a => a.id !== id)
      return true
    }
    catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to delete well activity'
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
