/**
 * Well rate book and out-of-AFE register types.
 *
 * A well's rates are copies, not references: once an item is added, later
 * master revisions cannot reach it. Locked rows are frozen to the approved AFE,
 * and any deviation after that is an out-of-AFE entry.
 */
import type { AuditFields } from '~/types/procurement'

export type RateBasis = 'daily' | 'per_service' | 'per_section' | 'fixed'
export type RateOrigin = 'well_planning' | 'unplanned'
export type RateStatus = 'draft' | 'locked'
export type UnplannedKind = 'service' | 'tangible' | 'other'
export type UnplannedStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'cancelled'
export type UnplannedReason =
  | 'emergency'
  | 'operational_necessity'
  | 'scope_change'
  | 'afe_omission'
  | 'rate_revision'
  | 'other'

export interface WellServiceRateRecord extends AuditFields {
  well_id: string
  service_id: string
  vendor_id: string | null
  currency_id: string
  unit_id: string
  hole_section_id: string | null
  rate_basis: RateBasis
  operating_rate: string
  standby_rate: string
  mobilisation_rate: string
  demobilisation_rate: string
  personnel_operating_rate: string
  personnel_standby_rate: string
  other_rate: string
  origin: RateOrigin
  status: RateStatus
  locked_at: string | null
  revision_number: number
  contract_reference: string | null
  notes: string | null
  is_active: boolean
  service_code: string | null
  service_name: string | null
  vendor_code: string | null
  vendor_name: string | null
  currency_code: string | null
  unit_code: string | null
  hole_section_code: string | null
}

export interface WellTangibleRateRecord extends AuditFields {
  well_id: string
  tangible_id: string
  vendor_id: string | null
  currency_id: string
  unit_id: string
  unit_rate: string
  master_price_id: string | null
  master_unit_rate: string | null
  master_effective_from: string | null
  is_overridden: boolean
  override_reason: string | null
  origin: RateOrigin
  status: RateStatus
  locked_at: string | null
  revision_number: number
  contract_reference: string | null
  notes: string | null
  is_active: boolean
  tangible_code: string | null
  tangible_name: string | null
  vendor_code: string | null
  vendor_name: string | null
  currency_code: string | null
  unit_code: string | null
  variance_to_master: string | null
}

export interface AvailableServiceRecord {
  id: string
  code: string
  name: string
  description: string | null
  cost_code_id: string | null
  cost_code: string | null
  default_unit_id: string | null
  default_unit_code: string | null
  in_rate_book: boolean
}

export interface AvailableTangibleRecord extends AvailableServiceRecord {
  master_price_id: string | null
  master_unit_rate: string | null
  master_currency_id: string | null
  master_currency_code: string | null
  master_unit_id: string | null
  master_unit_code: string | null
  master_vendor_id: string | null
  master_effective_from: string | null
}

export interface WellRateRevisionRecord extends AuditFields {
  well_id: string
  scope: 'service' | 'tangible'
  well_service_rate_id: string | null
  well_tangible_rate_id: string | null
  item_code: string
  item_name: string
  change_type:
    | 'added'
    | 'rate_revised'
    | 'details_updated'
    | 'locked'
    | 'deactivated'
    | 'unplanned_added'
  revision_number: number
  previous_rates: Record<string, unknown> | null
  new_rates: Record<string, unknown> | null
  reason: string | null
  effective_from: string | null
}

export interface RateBookLockResult {
  well_id: string
  locked_at: string
  reference: string | null
  locked_services: number
  locked_tangibles: number
}

export interface WellUnplannedItemRecord extends AuditFields {
  well_id: string
  reference: string
  afe_snapshot_id: string | null
  item_kind: UnplannedKind
  catalog_item_id: string | null
  item_description: string
  well_service_rate_id: string | null
  well_tangible_rate_id: string | null
  cost_code_id: string | null
  vendor_id: string | null
  currency_id: string
  unit_id: string | null
  quantity: string
  unit_rate: string
  amount: string
  reason_code: UnplannedReason
  justification: string
  incurred_on: string
  source_document_reference: string | null
  status: UnplannedStatus
  submitted_at: string | null
  submitted_by: string | null
  decided_at: string | null
  decided_by: string | null
  decision_note: string | null
  is_active: boolean
  catalog_item_code: string | null
  vendor_code: string | null
  currency_code: string | null
  unit_code: string | null
  cost_code: string | null
}

export interface WellCostExposure {
  well_id: string
  well_code: string
  well_name: string
  rig_name: string | null
  well_status: string
  rates_locked_at: string | null
  currency_code: string | null
  afe_number: string | null
  afe_total: string
  approved_unplanned_total: string
  pending_unplanned_total: string
  committed_total: string
  variance_amount: string
  variance_percent: string | null
  approved_unplanned_count: number
  pending_unplanned_count: number
  rate_book_services: number
  rate_book_tangibles: number
}

export const RATE_BASES = [
  { label: 'Daily rate', value: 'daily' },
  { label: 'Per service', value: 'per_service' },
  { label: 'Per section', value: 'per_section' },
  { label: 'Fixed rate', value: 'fixed' },
]

export const UNPLANNED_REASONS = [
  { label: 'Emergency', value: 'emergency' },
  { label: 'Operational necessity', value: 'operational_necessity' },
  { label: 'Scope change', value: 'scope_change' },
  { label: 'Omitted from the AFE', value: 'afe_omission' },
  { label: 'Rate revision', value: 'rate_revision' },
  { label: 'Other', value: 'other' },
]

export const UNPLANNED_KINDS = [
  { label: 'Service', value: 'service' },
  { label: 'Tangible', value: 'tangible' },
  { label: 'Other', value: 'other' },
]
