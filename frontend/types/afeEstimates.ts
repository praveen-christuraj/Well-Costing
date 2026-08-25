/** AFE Cost Estimates — well-scoped unit rates priced against AFE lines. */

export interface AfeCostEstimateLine {
  afe_line_id: string
  estimate_line_id: string | null
  line_number: number
  catalog_item_id: string | null
  catalog_item_code: string | null
  catalog_item_name: string | null
  item_type: string | null
  cost_code_id: string
  cost_code: string | null
  hole_section_id: string | null
  hole_section_code: string | null
  applies_to_all_sections: boolean
  rate_basis: string
  quantity: string | number
  unit_id: string
  unit_code: string | null
  unit_rate: string | number
  estimated_amount: string | number
  vendor_id: string | null
  vendor_name: string | null
  remarks: string | null
  notes: string | null
  rate_saved_at: string | null
}

export interface AfeCostEstimateGroupTotal {
  key: string
  label: string
  line_count: number
  estimated_total: string | number
}

export interface AfeCostEstimate {
  afe_id: string
  afe_code: string
  afe_title: string
  afe_status: string
  revision_number: number
  project_code: string | null
  project_name: string | null
  well_id: string
  well_code: string | null
  well_name: string | null
  rig_name: string | null
  budget_amount: string | number
  total_planned_days: string | number
  total_planned_depth: string | number
  depth_unit_code: string | null
  line_count: number
  priced_line_count: number
  unpriced_line_count: number
  estimated_total: string | number
  services_total: string | number
  consumables_total: string | number
  variance_to_budget: string | number
  lines: AfeCostEstimateLine[]
  totals_by_section: AfeCostEstimateGroupTotal[]
  totals_by_item_type: AfeCostEstimateGroupTotal[]
  totals_by_cost_code: AfeCostEstimateGroupTotal[]
  totals_by_rate_basis: AfeCostEstimateGroupTotal[]
}

export interface AfeCostEstimateRateInput {
  afe_line_id: string
  unit_rate: number
  vendor_id?: string | null
  remarks?: string | null
}
