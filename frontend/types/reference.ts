/**
 * Types for the configurable dropdown registry.
 *
 * A *slot* is a named picker in the UI; a *source* is a list it can read from.
 * Screens resolve options by slot code, so where a dropdown gets its data is a
 * super-admin configuration decision rather than a code change.
 */

export interface ReferenceSource {
  code: string
  label: string
  kind: 'master_data' | 'catalog' | 'procurement' | 'static' | 'well_scoped'
  entity: string | null
  description: string
  parent_field: string | null
  parent_source: string | null
  filterable: string[]
}

export interface DropdownBinding {
  id: string
  slot_code: string
  source_code: string
  filters: Record<string, unknown>
  label_template: string | null
  sort_by: string | null
  include_inactive: boolean
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DropdownSlot {
  code: string
  module: string
  label: string
  description: string
  default_source: string
  allowed_sources: string[]
  cascades_from: string | null
  locked: boolean
  effective_source: string
  is_overridden: boolean
  binding: DropdownBinding | null
  label_template: string
  filters: Record<string, unknown>
}

export interface DropdownRegistry {
  modules: { key: string, label: string }[]
  sources: ReferenceSource[]
  slots: DropdownSlot[]
}

export interface ReferenceOption {
  value: string
  label: string
  code: string | null
  name: string | null
  parent_id: string | null
  meta: Record<string, string>
}

export interface ReferenceOptions {
  slot: string
  source: string
  total: number
  options: ReferenceOption[]
}

export interface DropdownBindingWrite {
  source_code: string
  filters?: Record<string, unknown>
  label_template?: string | null
  sort_by?: string | null
  include_inactive?: boolean
  notes?: string | null
}

/** Slot codes the application references by name. */
export const SLOT = {
  catalogueItemPrimary: 'catalogue.item.primary_category',
  catalogueItemSecondary: 'catalogue.item.secondary_category',
  catalogueItemTertiary: 'catalogue.item.tertiary_category',
  catalogueItemUnit: 'catalogue.item.unit',
  costCategoryPrimary: 'cost_category.primary_category',
  costCategorySecondary: 'cost_category.secondary_category',
  costCodeCategory: 'cost_code.cost_category',
  afeSectionPhase: 'afe.section.phase',
  afeSectionHoleSection: 'afe.section.hole_section',
  afeLinePrimary: 'afe.line.primary_category',
  afeLineSecondary: 'afe.line.secondary_category',
  afeLineTertiary: 'afe.line.tertiary_category',
  afeLineItem: 'afe.line.item',
  afeLineCostCode: 'afe.line.cost_code',
  afeLineUnit: 'afe.line.unit',
  dailyCostPhase: 'daily_cost.phase',
  dailyCostHoleSection: 'daily_cost.hole_section',
  dailyCostActivity: 'daily_cost.activity',
  dailyCostSubActivity: 'daily_cost.sub_activity',
  dailyCostServiceItem: 'daily_cost.service_item',
  dailyCostConsumableItem: 'daily_cost.consumable_item',
} as const
