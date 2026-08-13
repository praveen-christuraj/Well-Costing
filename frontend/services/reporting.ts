import type { ApiClient } from '~/services/apiClient'
import type { CostOverviewReport, ReportFilters, ReportingContract } from '~/types/reporting'
function query(filters: ReportFilters): string { const params = new URLSearchParams(); Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value) }); const text = params.toString(); return text ? `?${text}` : '' }
export class ReportingApi {
  constructor(private readonly api: ApiClient) {}
  contract(): Promise<ReportingContract> { return this.api.get('/reports/contracts/v1') }
  overview(filters: ReportFilters): Promise<CostOverviewReport> { return this.api.get(`/reports/cost-overview${query(filters)}`) }
  export(filters: ReportFilters): Promise<Blob> { return this.api.download(`/reports/cost-overview/export${query(filters)}`) }
}
