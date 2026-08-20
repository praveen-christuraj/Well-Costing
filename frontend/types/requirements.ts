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

export interface RequirementItemRecord {
  id: string
  requirement_id: string
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
  section_name: string | null
  planned_duration_days: string | null
  planned_depth_from: string | null
  planned_depth_to: string | null
  depth_unit_id: string | null
  depth_unit_code: string | null
  notes: string | null
  is_active: boolean
}

export interface RequirementRecord {
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
  items: RequirementItemRecord[]
}

export interface EditableRequirementItem {
  id?: string
  line_number: number
  catalog_item_id: string
  cost_code_id: string
  quantity: string
  unit_id: string
  section_name: string
  planned_duration_days: string
  planned_depth_from: string
  planned_depth_to: string
  depth_unit_id: string
  notes: string
  is_active: boolean
  _state: 'clean' | 'new' | 'dirty'
}

export interface RequirementLookups {
  items: MasterDataRecord[]
  costCodes: MasterDataRecord[]
  units: MasterDataRecord[]
}
