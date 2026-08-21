import type { ApiClient } from '~/services/apiClient'
import type {
  DailyCostAnalytics,
  DailyCostEntry,
  ReferenceRatesData,
} from '~/types/dailyCost'

export class DailyCostApi {
  constructor(private readonly api: ApiClient) {}

  listEntries(wellId: string): Promise<DailyCostEntry[]> {
    return this.api.get(`/wells/${wellId}/daily-cost`)
  }

  getEntry(wellId: string, entryDate: string): Promise<DailyCostEntry | null> {
    return this.api.get(`/wells/${wellId}/daily-cost/entry?entry_date=${entryDate}`)
  }

  saveEntry(wellId: string, payload: Record<string, unknown>): Promise<DailyCostEntry> {
    return this.api.post(`/wells/${wellId}/daily-cost`, payload)
  }

  deleteEntry(wellId: string, entryId: string): Promise<undefined> {
    return this.api.delete(`/wells/${wellId}/daily-cost/${entryId}`)
  }

  getAnalytics(wellId: string): Promise<DailyCostAnalytics> {
    return this.api.get(`/wells/${wellId}/daily-cost/analytics`)
  }

  getReferenceRates(wellId: string): Promise<ReferenceRatesData> {
    return this.api.get(`/wells/${wellId}/daily-cost/reference-rates`)
  }
}
