export type ServiceType =
  | 'operation'
  | 'standby'
  | 'mobilisation'
  | 'demobilisation'
  | 'personnel_operation'
  | 'personnel_standby'
  | 'other'

export const SERVICE_TYPES: { label: string, value: ServiceType }[] = [
  { label: 'Equipment Operation', value: 'operation' },
  { label: 'Equipment Standby', value: 'standby' },
  { label: 'Mobilization', value: 'mobilisation' },
  { label: 'Demobilization', value: 'demobilisation' },
  { label: 'Personnel Operation', value: 'personnel_operation' },
  { label: 'Personnel Standby', value: 'personnel_standby' },
  { label: 'Others', value: 'other' },
]

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
  sub_activity_id?: string | null
  sub_activity_name?: string | null
  service_type: ServiceType
  service_hours: number | string
  operating_days: number | string
  rate_basis: 'daily' | 'per_service' | 'per_section' | 'fixed'
  unit_rate: number | string
  override_rate?: number | string | null
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
  sub_activity_id?: string | null
  sub_activity_name?: string | null
  quantity: number | string
  unit_id: string
  unit_code?: string | null
  unit_rate: number | string
  override_rate?: number | string | null
  amount: number | string
  remarks?: string | null
}

export interface ActivityRecord {
  id: string
  code: string
  name: string
  description: string | null
  sequence: number
  is_active: boolean
}

export interface WellActivityRecord {
  id: string
  well_id: string
  activity_id: string
  activity_code?: string | null
  activity_name?: string | null
  name: string
  responsible_party: string | null
  description: string | null
  is_active: boolean
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
  sub_activity_id?: string | null
  sub_activity_name?: string | null
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

export interface ActivityCostBreakdown {
  activity_id: string
  activity_code: string
  activity_name: string
  total_cost: number
  services_cost: number
  consumables_cost: number
  service_count: number
  consumable_count: number
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
  /** The governing AFE whose cost estimate supplies every unit rate. */
  afe_id?: string | null
  afe_code?: string | null
  afe_title?: string | null
  rates_source?: string
  priced_line_count?: number
  unpriced_line_count?: number
  services: ReferenceServiceRate[]
  consumables: ReferenceConsumableRate[]
}

/** One row of a planned-versus-actual grouping (section, activity, phase, …). */
export interface ComparisonBucket {
  key: string
  label: string
  entry_count: number
  services_cost: string | number
  consumables_cost: string | number
  total_cost: string | number
  planned_cost: string | number | null
  variance: string | number | null
  planned_days: string | number | null
  actual_days: string | number | null
  activity_code: string | null
  activity_name: string | null
  responsible_party: string | null
}

export interface DateComparisonPoint {
  entry_date: string
  day_number: number
  phase: string | null
  hole_section_code: string | null
  activity_name: string | null
  services_cost: string | number
  consumables_cost: string | number
  daily_cost: string | number
  cumulative_cost: string | number
  planned_cumulative: string | number | null
  current_depth: string | number | null
  daily_progress: string | number | null
}

/** Well-scoped cost comparison across every reporting dimension. */
export interface DailyCostComparison {
  well_id: string
  well_code: string | null
  well_name: string | null
  afe_id: string | null
  afe_code: string | null
  afe_title: string | null
  afe_budget: string | number
  estimate_total: string | number
  cumulative_actual_cost: string | number
  variance_to_budget: string | number
  variance_to_estimate: string | number
  total_planned_days: string | number
  days_elapsed: number
  by_date: DateComparisonPoint[]
  by_week: ComparisonBucket[]
  by_month: ComparisonBucket[]
  by_section: ComparisonBucket[]
  by_phase: ComparisonBucket[]
  by_activity: ComparisonBucket[]
  by_sub_activity: ComparisonBucket[]
}
