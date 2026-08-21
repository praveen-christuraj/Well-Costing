export interface AfeSnapshotAttempt {
  id: string
  estimate_version_id: string
  resulting_snapshot_id: string | null
  requested_reference: string | null
  status: 'completed' | 'blocked' | 'denied' | 'failed'
  message: string | null
  eligibility_snapshot: Record<string, unknown>
  created_at: string
  created_by: string | null
}

export interface AfeSnapshotLine {
  id: string
  line_number: number
  item_code: string
  item_description: string
  cost_code: string
  quantity: string
  unit_code: string
  total_cost: string
}

export interface AfeSnapshot {
  id: string
  afe_number: string
  snapshot_type: 'baseline'
  estimate_version_id: string
  calculation_run_id: string
  issue_date: string
  currency_code: string
  grand_total: string
  engine_version: string
  rule_set_version: string
  lines: AfeSnapshotLine[]
  created_at: string
  created_by: string | null
}

export interface EstimateAfeStatus {
  estimate_id: string
  estimate_version_id: string
  version_number: number
  afe_status: 'policy_pending' | 'issued'
  baseline_snapshot: AfeSnapshot | null
  creation_attempts: AfeSnapshotAttempt[]
  pending_requirements: string[]
}
