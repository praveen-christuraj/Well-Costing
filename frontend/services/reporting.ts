import type { ApiClient } from '~/services/apiClient'
import type { GeneratedReport, ReportFilters, ReportingContract } from '~/types/reporting'

function query(filters: ReportFilters): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, String(value))
  })
  return `?${params.toString()}`
}

export class ReportingApi {
  constructor(private readonly api: ApiClient) {}

  contract(): Promise<ReportingContract> {
    return this.api.get('/reports/contracts/v1')
  }

  generate(filters: ReportFilters): Promise<GeneratedReport> {
    return this.api.get(`/reports/generate${query(filters)}`)
  }

  export(filters: ReportFilters): Promise<Blob> {
    return this.api.download(`/reports/export${query(filters)}`)
  }
}
