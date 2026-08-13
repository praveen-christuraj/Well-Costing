import type { BulkRowError } from '~/types/masterData'

export interface ImportPreview {
  batch_id: string
  entity_type: string
  status: 'validated' | 'invalid'
  mapping_profile: string
  mapping_version: string
  detected_columns: string[]
  applied_mapping: Record<string, string>
  total_rows: number
  valid_rows: number
  error_rows: number
  errors: BulkRowError[]
  sample: Record<string, unknown>[]
}

export interface ImportCommitResult {
  batch_id: string
  status: 'committed'
  imported_rows: number
}

export interface ImportErrorRecord {
  id: string
  row_number: number
  column_name: string | null
  error_code: string
  message: string
  raw_value: unknown | null
}

export interface ImportBatch {
  id: string
  entity_type: string
  filename: string
  mapping_profile: string
  mapping_version: string
  status: string
  total_rows: number
  valid_rows: number
  error_rows: number
  imported_rows: number
  created_at: string
  created_by: string | null
  errors: ImportErrorRecord[]
}
