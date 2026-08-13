export interface CalculationRun {
  id: string
  estimate_version_id: string
  engine_version: string
  rule_set_version: string
  status: 'started' | 'completed' | 'blocked' | 'failed'
  message: string | null
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}
export interface CalculationResults {
  estimate_id: string
  estimate_version_id: string
  version_number: number
  currency_code: string
  base_total: string | null
  contingency_total: string | null
  escalation_total: string | null
  grand_total: string | null
  calculation_status: string
  line_results: Record<string, unknown>[]
  category_results: Record<string, unknown>[]
  calculation_runs: CalculationRun[]
  pending_rules: string[]
}
