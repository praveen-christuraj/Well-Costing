export type CostState = 'field_estimate' | 'commitment' | 'accrual' | 'actual' | 'forecast'
export type CorrectionKind = 'original' | 'reversal' | 'adjustment'

export interface CostControlLineInput {
  transaction_date: string
  source_document_type: string
  source_document_reference: string
  external_transaction_id: string | null
  cost_code: string
  vendor_code: string | null
  description: string
  quantity: string | null
  unit_code: string | null
  currency_code: string
  amount: string
  correction_kind: CorrectionKind
  reverses_transaction_id: string | null
}

export interface CostControlBatch {
  id: string
  estimate_version_id: string
  afe_snapshot_id: string | null
  cost_state: CostState
  source_type: 'manual' | 'excel'
  filename: string | null
  status: 'invalid' | 'validated' | 'blocked' | 'committed'
  total_rows: number
  valid_rows: number
  error_rows: number
  posted_rows: number
  staged_lines: Array<CostControlLineInput & { id: string, row_number: number }>
  errors: Array<{ id: string, row_number: number, error_code: string, message: string }>
  post_attempts: Array<{ id: string, status: string, message: string | null, created_at: string }>
  created_at: string
}

export interface CostControlBatchPage {
  items: CostControlBatch[]
  total: number
}
