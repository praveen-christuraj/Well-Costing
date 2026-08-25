export type ReportType =
  | 'afe_register'
  | 'afe_cost_estimate'
  | 'daily_cost'
  | 'cost_performance'
  | 'well_activities'

export interface ReportFilters {
  report_type: ReportType
  project_id?: string | undefined
  well_id?: string | undefined
  afe_id?: string | undefined
  date_from?: string | undefined
  date_to?: string | undefined
}

export interface ReportColumn {
  key: string
  label: string
  format: 'text' | 'number' | 'money' | 'date' | 'status'
}

export interface ReportSummary {
  key: string
  label: string
  value: string | number | null
  format: 'text' | 'number' | 'money'
}

export interface GeneratedReport {
  report_type: ReportType
  title: string
  description: string
  generated_at: string
  filters: ReportFilters
  columns: ReportColumn[]
  rows: Array<Record<string, string | number | null>>
  summaries: ReportSummary[]
}

export interface ReportingContract {
  contract_version: string
  contract_status: string
  schema_name: string
  direct_grants_status: string
  transactional_schema_public: boolean
  views: Array<{ name: string, kind: string, description: string }>
  pending_metrics: string[]
}
