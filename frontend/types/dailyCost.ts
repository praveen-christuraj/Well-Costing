export interface DailyCostServiceLine {
  id?: string
  daily_cost_entry_id?: string
  service_id: string
  service_code?: string | null
  service_name?: string | null
  cost_code_id: string
  cost_code?: string | null
  vendor_id?: string | null
  vendor_name?: string | null
  hole_section_id?: string | null
  hole_section_code?: string | null
  service_hours: number | string
  operating_days: number | string
  rate_basis: 'daily' | 'per_service' | 'per_section' | 'fixed'
  unit_rate: number | string
  amount: number | string
  remarks?: string | null
}

export interface DailyCostConsumableLine {
  id?: string
  daily_cost_entry_id?: string
  consumable_id: string
  consumable_code?: string | null
  consumable_name?: string | null
  cost_code_id: string
  cost_code?: string | null
  vendor_id?: string | null
  vendor_name?: string | null
  quantity: number | string
  unit_id: string
  unit_code?: string | null
  unit_rate: number | string
  amount: number | string
  remarks?: string | null
}

export interface DailyCostEntry {
  id: string
  well_id: string
  well_code?: string | null
  afe_id?: string | null
  afe_code?: string | null
  entry_date: string
  hole_section_id?: string | null
  hole_section_code?: string | null
  phase?: string | null
  current_depth?: number | string | null
  daily_progress?: number | string | null
  operational_summary?: string | null
  total_services_cost: number | string
  total_consumables_cost: number | string
  total_daily_cost: number | string
  cumulative_cost: number | string
  is_active: boolean
  services: DailyCostServiceLine[]
  consumables: DailyCostConsumableLine[]
  created_at?: string
  updated_at?: string
}

export interface DailyTrendPoint {
  entry_date: string
  daily_cost: number
  cumulative_cost: number
  services_cost: number
  consumables_cost: number
  phase?: string | null
  current_depth?: number | null
}

export interface ServiceBreakdownItem {
  service_id: string
  service_code: string
  service_name: string
  total_hours: number
  total_days: number
  total_cost: number
  percentage: number
}

export interface ConsumableBreakdownItem {
  consumable_id: string
  consumable_code: string
  consumable_name: string
  unit_code: string
  total_quantity: number
  total_cost: number
  percentage: number
}

export interface DailyCostAnalytics {
  well_id: string
  well_code: string
  afe_id?: string | null
  afe_code?: string | null
  afe_budget: number
  total_planned_days: number
  cumulative_actual_cost: number
  balance_amount: number
  days_elapsed: number
  burn_rate_daily_avg: number
  remaining_planned_days: number
  forecast_at_end_of_well: number
  variance_to_afe: number
  trend_last_5_days: DailyTrendPoint[]
  trend_last_7_days: DailyTrendPoint[]
  trend_all_days: DailyTrendPoint[]
  services_breakdown: ServiceBreakdownItem[]
  consumables_breakdown: ConsumableBreakdownItem[]
}

export interface ReferenceServiceRate {
  service_id: string
  service_code: string
  service_name: string
  cost_code_id: string
  cost_code: string
  vendor_id?: string | null
  vendor_name?: string | null
  rate_basis: 'daily' | 'per_service' | 'per_section' | 'fixed'
  operating_rate: number
  unit_code: string
}

export interface ReferenceConsumableRate {
  consumable_id: string
  consumable_code: string
  consumable_name: string
  item_type: string
  cost_code_id: string
  cost_code: string
  unit_id: string
  unit_code: string
  unit_rate: number
}

export interface ReferenceRatesData {
  services: ReferenceServiceRate[]
  consumables: ReferenceConsumableRate[]
}
