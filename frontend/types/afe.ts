import type { MasterDataRecord } from '~/types/masterData'

export interface ProjectRecord {
  id: string
  code: string
  name: string
  description: string | null
  is_active: boolean
}

export interface WellRecord {
  id: string
  project_id: string
  /** Null when the referenced project was hard-deleted. */
  project_code: string | null
  code: string
  name: string
  description: string | null
  rig_name: string | null
  status: 'planning' | 'active' | 'suspended' | 'completed' | 'abandoned'
  spud_date: string | null
  completion_date: string | null
  rates_locked_at: string | null
  rate_lock_reference: string | null
  is_active: boolean
}

export interface DrillingPhaseRecord {
  id: string
  code: string
  name: string
  description: string | null
  sequence: number
  is_active: boolean
}

export interface AfeSectionRecord {
  id: string
  afe_id: string
  sequence: number
  hole_section_id: string | null
  hole_section_code?: string | null
  hole_section_name?: string | null
  phase: string
  planned_days: number | string
  planned_depth_from?: number | string | null
  planned_depth_to?: number | string | null
  depth_unit_id?: string | null
  depth_unit_code?: string | null
  notes?: string | null
  is_active: boolean
}

export interface EditableAfeSection {
  id?: string
  sequence: number
  hole_section_id: string
  phase: string
  planned_days: number | null
  planned_depth_from: number | null
  planned_depth_to: number | null
  depth_unit_id: string
  notes: string
  is_active: boolean
  _state?: 'clean' | 'new' | 'dirty'
}

export interface AfeAuditLogRecord {
  id: string
  afe_id: string
  action: string
  previous_status: string | null
  new_status: string
  remarks: string | null
  actor_id: string | null
  created_at: string
}

/** How a line is charged. Services take the first four; chemicals the last two. */
export type RateBasis =
  | 'daily'
  | 'per_service'
  | 'per_section'
  | 'fixed'
  | 'per_unit'
  | 'daily_consumption'

export const SERVICE_RATE_BASES: { label: string, value: RateBasis }[] = [
  { label: 'Daily rate', value: 'daily' },
  { label: 'Per section', value: 'per_section' },
  { label: 'Per service', value: 'per_service' },
  { label: 'Fixed', value: 'fixed' },
]

export const CONSUMABLE_RATE_BASES: { label: string, value: RateBasis }[] = [
  { label: 'Per unit', value: 'per_unit' },
  { label: 'Daily usage', value: 'daily_consumption' },
]

export const ALL_RATE_BASES = [...SERVICE_RATE_BASES, ...CONSUMABLE_RATE_BASES]

/** Catalogue item types planned as consumption rather than as a service. */
export const CONSUMABLE_ITEM_TYPES = ['mud_chemical', 'cement_additive']

/** Bases offered for a catalogue item type — mirrors the backend rule. */
export function rateBasesFor(itemType?: string | null): { label: string, value: RateBasis }[] {
  if (itemType && CONSUMABLE_ITEM_TYPES.includes(itemType)) return CONSUMABLE_RATE_BASES
  if (itemType === 'service') return SERVICE_RATE_BASES
  return ALL_RATE_BASES.filter(basis => basis.value === 'per_unit' || basis.value === 'fixed')
}

export function defaultRateBasisFor(itemType?: string | null, catalogueBasis?: string | null): RateBasis {
  const allowed = rateBasesFor(itemType).map(basis => basis.value)
  if (catalogueBasis && allowed.includes(catalogueBasis as RateBasis)) return catalogueBasis as RateBasis
  if (itemType === 'service' || itemType === 'equipment') return 'daily'
  return allowed[0] ?? 'per_unit'
}

export interface AfeLineRecord {
  id: string
  afe_id: string
  line_number: number
  catalog_item_id: string
  catalog_item_code: string | null
  catalog_item_name: string | null
  item_type: string | null
  cost_code_id: string
  cost_code: string | null
  quantity: string
  unit_id: string
  unit_code: string | null
  hole_section_id: string | null
  hole_section_code: string | null
  hole_section_name: string | null
  rate_basis: RateBasis
  daily_consumption: string | null
  computed_quantity: string | null
  quantity_override_reason: string | null
  quantity_source: 'entered' | 'computed' | 'overridden'
  planned_duration_days: string | null
  planned_depth_from: string | null
  planned_depth_to: string | null
  depth_unit_id: string | null
  depth_unit_code: string | null
  notes: string | null
  is_active: boolean
}

export interface AfeRecord {
  id: string
  well_id: string
  /** Null when the referenced well/project was hard-deleted. */
  well_code: string | null
  project_id: string | null
  project_code: string | null
  code: string
  title: string
  description: string | null
  status: 'draft' | 'submitted'
  revision_number: number
  budget_amount: string | number
  total_planned_days: string | number
  total_planned_depth: string | number
  depth_unit_id: string | null
  depth_unit_code?: string | null
  reopen_remarks?: string | null
  reopened_at?: string | null
  reopened_by?: string | null
  submitted_at: string | null
  deleted_at?: string | null
  deleted_by?: string | null
  is_active: boolean
  item_count: number
  sections: AfeSectionRecord[]
  items: AfeLineRecord[]
  audit_logs: AfeAuditLogRecord[]
}

export interface EditableAfeLine {
  id?: string
  line_number: number
  catalog_item_id: string
  cost_code_id: string
  quantity: string
  unit_id: string
  hole_section_id: string
  rate_basis: RateBasis
  daily_consumption: string
  computed_quantity: string
  quantity_override_reason: string
  planned_duration_days: string
  planned_depth_from: string
  planned_depth_to: string
  depth_unit_id: string
  notes: string
  is_active: boolean
  _state: 'clean' | 'new' | 'dirty'
}

export interface AfeLookups {
  items: MasterDataRecord[]
  costCodes: MasterDataRecord[]
  units: MasterDataRecord[]
  holeSections: MasterDataRecord[]
  phases?: DrillingPhaseRecord[]
}
