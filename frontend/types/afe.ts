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
  project_code: string
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
  catalog_item_code: string
  catalog_item_name: string
  item_type: string
  cost_code_id: string
  cost_code: string
  quantity: string
  unit_id: string
  unit_code: string
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
  well_code: string
  project_id: string
  project_code: string
  code: string
  title: string
  description: string | null
  status: 'draft' | 'submitted'
  revision_number: number
  submitted_at: string | null
  is_active: boolean
  item_count: number
  items: AfeLineRecord[]
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
}
