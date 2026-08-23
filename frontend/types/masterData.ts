export interface MasterDataRecord {
  id: string
  code: string
  name: string
  description: string | null
  is_active: boolean
  symbol?: string | null
  parent_id?: string | null
  parent_code?: string | null
  cost_category_id?: string | null
  cost_category_code?: string | null
  cost_code_id?: string | null
  cost_code?: string | null
  default_unit_id?: string | null
  default_unit_code?: string | null
  primary_category_id?: string | null
  primary_category_code?: string | null
  primary_category_name?: string | null
  secondary_category_id?: string | null
  secondary_category_code?: string | null
  secondary_category_name?: string | null
  tertiary_category_id?: string | null
  tertiary_category_code?: string | null
  tertiary_category_name?: string | null
  sequence?: number | null
  rate_basis?: string | null
  material_number?: string | null
  specification?: string | null
  manufacturer?: string | null
  vendor_type?: string | null
  contact_person?: string | null
  email?: string | null
  phone?: string | null
  country?: string | null
  item_type?: string | null
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}

export interface EditableMasterDataRow {
  id?: string
  code: string
  name: string
  description: string
  is_active: boolean
  symbol?: string
  parent_id?: string
  cost_category_id?: string
  cost_code_id?: string
  default_unit_id?: string
  primary_category_id?: string
  secondary_category_id?: string
  tertiary_category_id?: string
  _state: 'clean' | 'new' | 'dirty'
}

/** What a permanent delete removes alongside the record itself. */
export interface DeleteCascade {
  entity: string
  label: string
  count: number
}

export interface DeleteImpact {
  entity: string
  id: string
  code: string
  name: string
  cascades: DeleteCascade[]
  blockers: string[]
  requires_confirmation: boolean
}

export interface PageResponse<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  pages: number
}

export interface BulkRowError {
  row_index: number
  column: string | null
  code: string
  message: string
}

export interface BulkValidationResult {
  valid: boolean
  total_rows: number
  valid_rows: number
  errors: BulkRowError[]
}

export interface RateRecord {
  id: string
  item_id: string
  item_code: string
  item_type: string
  vendor_id: string
  vendor_code: string
  currency_id: string
  currency_code: string
  unit_id: string
  unit_code: string
  amount: string
  effective_from: string
  effective_to: string | null
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface EditableRateRow {
  id?: string
  item_id: string
  vendor_id: string
  currency_id: string
  unit_id: string
  amount: string
  effective_from: string
  effective_to: string
  description: string
  is_active: boolean
  _state: 'clean' | 'new' | 'dirty'
}

export interface CostLibraryEntity {
  key: string
  label: string
  singular: string
  phase: number
  supportsSymbol?: boolean
}

export const costLibraryEntities: CostLibraryEntity[] = [
  { key: 'catalog-items', label: 'Catalogue Items', singular: 'catalogue item', phase: 2 },
  { key: 'primary-categories', label: 'Primary Categories', singular: 'primary category', phase: 2 },
  { key: 'secondary-categories', label: 'Secondary Categories', singular: 'secondary category', phase: 2 },
  { key: 'tertiary-categories', label: 'Tertiary Categories', singular: 'tertiary category', phase: 2 },
  { key: 'mud-chemicals', label: 'Mud Chemicals', singular: 'mud chemical', phase: 2 },
  { key: 'cement-additives', label: 'Cement Additives', singular: 'cement additive', phase: 2 },
  { key: 'tangibles', label: 'Tangibles', singular: 'tangible', phase: 2 },
  { key: 'materials', label: 'Materials', singular: 'material', phase: 2 },
  { key: 'equipment', label: 'Equipment', singular: 'equipment item', phase: 2 },
  { key: 'vendors', label: 'Vendors', singular: 'vendor', phase: 2 },
  { key: 'rates', label: 'Rates', singular: 'rate', phase: 2 },
  { key: 'units', label: 'Units', singular: 'unit', phase: 2, supportsSymbol: true },
  { key: 'currencies', label: 'Currencies', singular: 'currency', phase: 2, supportsSymbol: true },
  { key: 'cost-categories', label: 'Cost Categories', singular: 'cost category', phase: 2 },
  { key: 'cost-codes', label: 'Cost Codes', singular: 'cost code', phase: 2 },
]
