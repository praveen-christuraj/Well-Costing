/**
 * Type contracts for the Daily Costs, Cost Analytics and Cost Reports pages.
 *
 * Every money value arrives from the API as a decimal string (`"1234.50"`) and
 * is sent back the same way, so nothing is ever rounded in the browser: the
 * server prices a day and the page only displays what came back.
 */

import type { ChargingBasis, QuantityUnit } from '~/types/afe'

export type { ChargingBasis, QuantityUnit }

export type DailyStatus = 'draft' | 'submitted'
export type ReconciliationStatus = 'pending' | 'reconciled'

/** The four consumable categories entered on a day. */
export type ConsumableCategory = 'mud_chemical' | 'fuel' | 'cement_additive' | 'drill_bit'

export const CONSUMABLE_CATEGORIES: ConsumableCategory[] = [
  'mud_chemical',
  'fuel',
  'cement_additive',
  'drill_bit',
]

export const CONSUMABLE_LABELS: Record<ConsumableCategory, string> = {
  mud_chemical: 'Mud Chemicals',
  fuel: 'Fuel',
  cement_additive: 'Cement Additives',
  drill_bit: 'Drill Bits',
}

/** How each consumable category is entered on a day. */
export const CONSUMABLE_ENTRY_HINTS: Record<ConsumableCategory, string> = {
  mud_chemical: 'Pick the chemical from Master Data and enter the quantity used — the unit rate is captured from the catalogue.',
  fuel: 'Enter the usage only — the fuel unit rate is captured from the AFE cost estimate.',
  cement_additive: 'Enter the total consumption cost for the selected section, phase and sub activity.',
  drill_bit: 'Pick the drill bit and enter the number used — the unit rate is captured from the catalogue.',
}

/** Categories where the AFE amount is a one-time charge, never multiplied. */
export const ONE_TIME_LABEL = 'One-time charge — not multiplied by hours or days'

/** Quantity limits enforced by the engine. */
export const MAX_HOURS = 24
export const MAX_DAYS = 1

// ---------------------------------------------------------------------------
// Context (what the well + AFE provide)
// ---------------------------------------------------------------------------

export interface RateCardRate {
  category: string
  unit_rate: string
  [key: string]: unknown
}

export interface RateCardSectionRate {
  section_id: number
  phase_id: number | null
  amount: string
  section_label?: string | null
  [key: string]: unknown
}

/** One service of the selected AFE, with everything the daily page prices from. */
export interface RateCardService {
  service_id: number
  afe_line_id: number | null
  service_code: string
  service_name: string
  provider_type: string
  charging_basis: ChargingBasis
  per_service_amount: string
  section_id: number | null
  phase_id: number | null
  rates: RateCardRate[]
  section_rates: RateCardSectionRate[]
}

export interface DailyCostAfeOption {
  id: number
  afe_code: string
  afe_name: string
  afe_type?: string
  status?: string
  estimated_total?: string
  [key: string]: unknown
}

export interface DailyCostSubActivity {
  id: number
  sub_activity_code: string
  sub_activity_name: string
  activity_id: number | null
  activity_code?: string | null
  activity_name?: string | null
  [key: string]: unknown
}

export interface WellConfigurationSectionPhase {
  phase_id: number
  phase_code: string
  phase_name: string
  days: string
  [key: string]: unknown
}

export interface WellConfigurationSection {
  section_id: number
  section_code: string
  section_name: string
  from_depth: string | null
  to_depth: string | null
  phases: WellConfigurationSectionPhase[]
  [key: string]: unknown
}

export interface WellConfiguration {
  sections: WellConfigurationSection[]
  total_depth: string
  depth_unit: string
  total_days: string
  [key: string]: unknown
}

export interface DailyCostContext {
  well_id: number
  well_code: string
  well_name: string
  rig_id: number | null
  rig_code: string | null
  rig_name: string | null
  depth_unit: string
  well_configuration: WellConfiguration | null
  afes: DailyCostAfeOption[]
  sub_activities: DailyCostSubActivity[]
  rate_card: RateCardService[]
  afe_id: number | null
  /** Fuel unit rate captured on the selected AFE cost estimate. */
  fuel_rate: string
  /** The selected AFE's estimated total, to show what the day leaves behind. */
  afe_estimated_total: string
  warnings: string[]
}

// ---------------------------------------------------------------------------
// Day lines: the payloads and the read models
// ---------------------------------------------------------------------------

export interface DailyServiceLineIn {
  service_id: number | null
  charging_basis?: ChargingBasis | null
  charge_category?: string | null
  afe_line_id?: number | null
  section_id?: number | null
  phase_id?: number | null
  sub_activity_id?: number | null
  quantity?: string
  quantity_unit?: QuantityUnit
  captured_rate?: string | null
  override_rate?: string | null
  remarks?: string | null
}

export interface DailyConsumableLineIn {
  category: ConsumableCategory
  item_id?: number | null
  item_code?: string | null
  item_name?: string | null
  quantity?: string
  uom?: string | null
  currency?: string | null
  captured_rate?: string | null
  override_rate?: string | null
  manual_amount?: string | null
  section_id?: number | null
  phase_id?: number | null
  sub_activity_id?: number | null
  remarks?: string | null
}

export interface DailyTangibleLineIn {
  tangible_id: number | null
  quantity?: string
  uom?: string | null
  currency?: string | null
  captured_rate?: string | null
  override_rate?: string | null
  remarks?: string | null
}

export interface DailyCostSaveIn {
  services: DailyServiceLineIn[]
  consumables: DailyConsumableLineIn[]
  tangibles: DailyTangibleLineIn[]
  remarks?: string | null
}

export interface DailyCostPreviewIn extends DailyCostSaveIn {
  well_id: number
  afe_id?: number | null
}

export interface DailyServiceLine {
  id: number
  service_id: number
  service_code: string | null
  service_name: string | null
  provider_type: string | null
  afe_line_id: number | null
  charging_basis: ChargingBasis
  charge_category: string
  section_id: number | null
  phase_id: number | null
  sub_activity_id: number | null
  sub_activity_display: string | null
  quantity: string
  quantity_unit: string
  captured_rate: string
  override_rate: string | null
  amount: string
  remarks: string | null
}

export interface DailyConsumableLine {
  id: number
  category: ConsumableCategory
  item_id: number | null
  item_code: string
  item_name: string
  quantity: string
  uom: string | null
  currency: string | null
  captured_rate: string
  override_rate: string | null
  manual_amount: string | null
  amount: string
  section_id: number | null
  phase_id: number | null
  sub_activity_id: number | null
  sub_activity_display: string | null
  remarks: string | null
}

export interface DailyTangibleLine {
  id: number
  tangible_id: number
  tangible_code: string | null
  tangible_name: string | null
  quantity: string
  uom: string | null
  currency: string | null
  captured_rate: string
  override_rate: string | null
  amount: string
  remarks: string | null
}

export interface DailyCostEntry {
  id: number
  daily_cost_code: string
  rig_id: number
  well_id: number
  cost_date: string
  afe_id: number | null
  afe_code: string | null
  remarks: string | null
  status: DailyStatus
  submitted_at: string | null
  reconciliation_status: ReconciliationStatus
  reconciliation_ref: string | null
  reconciled_at: string | null
  is_deleted: boolean
  deleted_at: string | null
  created_at: string | null
  updated_at: string | null
  rig_code: string | null
  rig_name: string | null
  rig_display: string | null
  well_code: string | null
  well_name: string | null
  well_display: string | null
  service_count: number
  consumable_count: number
  tangible_count: number
  service_total: string
  consumable_total: string
  tangible_total: string
  total_cost: string
}

export interface SummaryRow {
  group: string
  amount: string
}

export interface DailyCostDay {
  entry: DailyCostEntry
  well_configuration: WellConfiguration | null
  services: DailyServiceLine[]
  consumables: DailyConsumableLine[]
  tangibles: DailyTangibleLine[]
  summary: SummaryRow[]
  grand_total: string
  warnings: string[]
}

/** One priced line of the server preview, matched back to the row on screen. */
export interface PreviewLine {
  line_id: number | null
  code: string
  name: string
  amount: string
  warnings: string[]
}

export interface DailyCostPreview {
  services: PreviewLine[]
  consumables: PreviewLine[]
  tangibles: PreviewLine[]
  summary: SummaryRow[]
  grand_total: string
  warnings: string[]
}

// ---------------------------------------------------------------------------
// Catalogue lookups the panels pick from
// ---------------------------------------------------------------------------

export interface MudChemicalOption {
  id: number
  chemical_code: string
  chemical_name: string
  current_rate: string | null
  uom: string | null
  currency: string | null
  [key: string]: unknown
}

export interface DrillBitOption {
  id: number
  bit_code: string
  bit_name: string
  final_cost: string | null
  uom: string | null
  currency: string | null
  [key: string]: unknown
}

export interface TangibleOption {
  id: number
  tangible_code: string
  tangible_name: string
  final_cost: string | null
  uom: string | null
  currency: string | null
  [key: string]: unknown
}

export interface ServiceOption {
  id: number
  service_code: string
  service_name: string
  provider_type: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Cost Analytics
// ---------------------------------------------------------------------------

export interface GroupComparison {
  group: string
  estimated: string
  actual: string
  balance: string
  variance_pct: string | null
  [key: string]: unknown
}

export interface CostForecast {
  actual_to_date: string
  estimated_total: string
  planned_days: string
  elapsed_days: string
  remaining_days: string
  burn_rate_per_day: string
  forecast_at_completion: string
  variance: string
  variance_pct: string | null
  balance_at_completion: string
  basis: string
}

export interface DepthCostPoint {
  depth: string
  section_id: number
  section_label: string
  estimated_cumulative: string
  actual_cumulative: string
  estimated_section: string
  actual_section: string
  variance: string
}

export interface WellAnalyticsSummary {
  well_id: number
  well_code: string
  well_name: string
  rig_id: number | null
  rig_code: string | null
  rig_name: string | null
  well_status: string
  depth_unit: string
  afe_count: number
  estimated_total: string
  estimated_services: string
  estimated_consumables: string
  estimated_tangibles: string
  actual_total: string
  actual_services: string
  actual_consumables: string
  actual_tangibles: string
  balance: string
  utilisation: string | null
  reconciled_total: string
  unreconciled_total: string
  planned_days: string
  elapsed_days: string
  days_with_cost: number
  first_cost_date: string | null
  last_cost_date: string | null
  forecast_at_completion: string
  forecast_variance: string
}

export interface DailyTrendPoint {
  cost_date: string
  amount: string
  cumulative: string
}

export interface DimensionRow {
  key: string
  label: string
  services: string
  consumables: string
  tangibles: string
  total: string
  estimated: string
  balance: string
}

export interface WellAnalytics {
  well: WellAnalyticsSummary
  afe_id: number | null
  afes: DailyCostAfeOption[]
  comparisons: GroupComparison[]
  forecast: CostForecast
  depth_series: DepthCostPoint[]
  depth_notes: string[]
  unattributed_actual: string
  dimensions: Record<string, DimensionRow[]>
  daily_trend: DailyTrendPoint[]
  warnings: string[]
}

// ---------------------------------------------------------------------------
// Cost Reports
// ---------------------------------------------------------------------------

export type ReportDimension =
  | 'date'
  | 'section'
  | 'phase'
  | 'activity'
  | 'sub_activity'
  | 'service'
  | 'charge_category'
  | 'consumable_category'
  | 'tangible'
  | 'well'

export interface ReportDimensionOption {
  dimension: ReportDimension
  title: string
}

export interface ReportRow {
  key: string
  label: string
  services: string
  consumables: string
  tangibles: string
  total: string
  estimated: string
  balance: string
  extra: Record<string, unknown>
}

export interface ReportTotals {
  services: string
  consumables: string
  tangibles: string
  total: string
  estimated: string
  balance: string
}

export interface CostReport {
  dimension: ReportDimension
  title: string
  filters: Record<string, unknown>
  rows: ReportRow[]
  totals: ReportTotals
  generated_at: string | null
}

/** One cost line behind a report row — the drill-through itself. */
export interface ReportLine {
  cost_date: string
  daily_cost_code: string
  well: string
  cost_group: string
  category: string
  code: string
  name: string
  section: string
  phase: string
  activity: string
  sub_activity: string
  quantity: string
  unit: string
  rate: string
  amount: string
  remarks: string
  status: DailyStatus
}

export interface ReportLineBundle {
  dimension: ReportDimension
  key: string | null
  line_count: number
  total: number
  lines: ReportLine[]
}
