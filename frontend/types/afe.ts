/** Type contracts for the AFE Management page and its API payloads. */

export type AfeType = 'Drilling' | 'Completion'
export type AfeStatus = 'draft' | 'submitted' | 'approved'
export type ChargingBasis = 'Daily Rate' | 'Per Service Rate' | 'Per Section Rate'
export type QuantityUnit = 'days' | 'hours'

/** The eight constant charge categories, in the order the UI shows them. */
export const CHARGE_CATEGORIES = [
  'Mobilization',
  'Demobilization',
  'Operation',
  'Standby',
  'Personnel-Operation',
  'Personnel-Standby',
  'Fixed Charge',
  'Others',
] as const

/** Charged once per service, never multiplied by days or sections. */
export const ONE_TIME_CATEGORIES = ['Mobilization', 'Demobilization', 'Fixed Charge'] as const

/** Categories a day quantity is entered against. */
export const DAY_BASED_CATEGORIES = [
  'Operation',
  'Standby',
  'Personnel-Operation',
  'Personnel-Standby',
  'Others',
] as const

export const CHARGING_BASES: ChargingBasis[] = ['Daily Rate', 'Per Service Rate', 'Per Section Rate']

export interface AfeRow {
  id: number
  afe_code: string
  afe_name: string
  afe_type: AfeType
  rig_id: number
  well_id: number
  remarks: string | null
  status: AfeStatus
  status_remarks: string | null
  submitted_at: string | null
  approved_at: string | null
  rig_code: string | null
  rig_name: string | null
  rig_display: string | null
  well_code: string | null
  well_name: string | null
  well_display: string | null
  service_count: number
  consumable_count: number
  tangible_count: number
  estimated_total: string | number
  is_deleted?: boolean
  deleted_at?: string | null
  [key: string]: unknown
}

export interface CostComponent {
  category: string
  description: string
  quantity: string | number | null
  rate: string | number | null
  unit: string | null
  amount: string | number
  section_label: string | null
  phase_label: string | null
}

export interface LineEstimate {
  amount: string | number
  components: CostComponent[]
  warnings: string[]
}

export interface ServiceRateRow {
  category: string
  unit_rate: string | number
}

export interface ServiceChargeRow {
  category: string
  quantity: string | number
  quantity_unit: QuantityUnit
}

export interface ServiceSectionRateRow {
  section_id: number
  phase_id: number | null
  amount: string | number
}

export interface ServiceLineRow {
  id: number
  service_id: number
  service_code: string | null
  service_name: string | null
  provider_type: string | null
  charging_basis: ChargingBasis
  section_id: number | null
  phase_id: number | null
  per_service_amount: string | number
  effective_date: string | null
  remarks: string | null
  rates: ServiceRateRow[]
  charge_lines: ServiceChargeRow[]
  section_rates: ServiceSectionRateRow[]
  estimate: LineEstimate
}

export interface ConsumableLineRow {
  id: number
  item_kind: 'mud_chemical' | 'drill_bit'
  item_id: number
  item_code: string
  item_name: string
  quantity: string | number
  captured_rate: string | number
  override_rate: string | number | null
  uom: string | null
  currency: string | null
  section_id: number | null
  phase_id: number | null
  remarks: string | null
  estimate: LineEstimate
}

export interface TangibleLineRow {
  id: number
  tangible_id: number
  tangible_code: string | null
  tangible_name: string | null
  quantity: string | number
  captured_rate: string | number
  override_rate: string | number | null
  uom: string | null
  currency: string | null
  remarks: string | null
  estimate: LineEstimate
}

export interface GroupSummary {
  group: string
  amount: string | number
  line_count: number
}

export interface SectionRollup {
  section_id: number | null
  section_label: string
  planned_days: string | number
  amount: string | number
}

export interface EstimateSection {
  id: number
  section_id: number
  section_code: string | null
  section_name: string | null
  from_depth: string | number
  to_depth: string | number
  remarks: string | null
  total_days: string | number
  phases: {
    id: number
    phase_id: number
    phase_code: string | null
    phase_name: string | null
    days: string | number
    remarks: string | null
  }[]
}

export interface EstimateWellConfiguration {
  well_id: number
  well_code: string
  well_name: string
  rig_code: string | null
  rig_name: string | null
  status: string
  config_status: string
  depth_unit: string
  total_depth: string | number | null
  total_days: string | number
  sections: EstimateSection[]
}

/** The read model behind the AFE Cost Estimation tab and its print sheet. */
export interface AfeEstimate {
  afe: AfeRow
  well_configuration: EstimateWellConfiguration | null
  services: ServiceLineRow[]
  consumables: ConsumableLineRow[]
  tangibles: TangibleLineRow[]
  summary: GroupSummary[]
  by_section: SectionRollup[]
  grand_total: string | number
  warnings: string[]
}

/** Payload accepted by `PUT /afe/estimates/{id}`. */
export interface EstimatePayload {
  [key: string]: unknown
  services: {
    service_id: number
    charging_basis: ChargingBasis
    section_id: number | null
    phase_id: number | null
    per_service_amount: string | number
    effective_date: string | null
    remarks: string | null
    rates: ServiceRateRow[]
    charge_lines: ServiceChargeRow[]
    section_rates: ServiceSectionRateRow[]
  }[]
  consumables: {
    item_kind: 'mud_chemical' | 'drill_bit'
    item_id: number
    quantity: string | number
    captured_rate: string | number
    override_rate: string | number | null
    uom: string | null
    currency: string | null
    section_id: number | null
    phase_id: number | null
    remarks: string | null
  }[]
  tangibles: {
    tangible_id: number
    quantity: string | number
    captured_rate: string | number
    override_rate: string | number | null
    uom: string | null
    currency: string | null
    remarks: string | null
  }[]
}

/** Master-data lookups used by the pickers. */
export interface ServiceOption {
  id: number
  service_code: string
  service_name: string
  provider_type: string
  vendor_display?: string | null
}

export interface ConsumableOption {
  id: number
  code: string
  name: string
  rate: number
  uom: string | null
  currency: string | null
  kind: 'mud_chemical' | 'drill_bit'
  detail: string
}

export interface TangibleOption {
  id: number
  code: string
  name: string
  rate: number
  uom: string | null
  currency: string | null
  detail: string
}
