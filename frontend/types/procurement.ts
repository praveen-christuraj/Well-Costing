export type RowState = 'clean' | 'new' | 'dirty'

export interface AuditFields {
  id: string
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}

export interface ServiceOrderRecord extends AuditFields {
  order_number: string
  title: string
  vendor_id: string
  currency_id: string | null
  valid_from: string
  valid_to: string | null
  contract_value: string | null
  status: string
  description: string | null
  is_active: boolean
  vendor_code: string | null
  vendor_name: string | null
  currency_code: string | null
}

export interface PurchaseOrderRecord extends AuditFields {
  order_number: string
  title: string
  vendor_id: string
  currency_id: string | null
  order_date: string
  expected_delivery_date: string | null
  order_value: string | null
  status: string
  description: string | null
  is_active: boolean
  vendor_code: string | null
  vendor_name: string | null
  currency_code: string | null
}

export interface ServiceRateRecord extends AuditFields {
  service_id: string
  vendor_id: string
  service_order_id: string | null
  currency_id: string
  unit_id: string
  hole_section: string | null
  operating_rate: string
  standby_rate: string
  mobilisation_rate: string
  demobilisation_rate: string
  effective_from: string
  effective_to: string | null
  description: string | null
  is_active: boolean
  service_code: string | null
  service_name: string | null
  vendor_code: string | null
  vendor_name: string | null
  service_order_number: string | null
  currency_code: string | null
  unit_code: string | null
}

export interface ItemPriceRecord extends AuditFields {
  item_id: string
  vendor_id: string
  purchase_order_id: string | null
  currency_id: string
  unit_id: string
  unit_price: string
  effective_from: string
  effective_to: string | null
  description: string | null
  is_active: boolean
  item_code: string | null
  item_name: string | null
  item_type: string | null
  vendor_code: string | null
  vendor_name: string | null
  purchase_order_number: string | null
  currency_code: string | null
  unit_code: string | null
}

export const SERVICE_ORDER_STATUSES = [
  { label: 'Draft', value: 'draft' },
  { label: 'Active', value: 'active' },
  { label: 'Expired', value: 'expired' },
  { label: 'Cancelled', value: 'cancelled' },
]

export const PURCHASE_ORDER_STATUSES = [
  { label: 'Draft', value: 'draft' },
  { label: 'Open', value: 'open' },
  { label: 'Partially received', value: 'partially_received' },
  { label: 'Closed', value: 'closed' },
  { label: 'Cancelled', value: 'cancelled' },
]

export const VENDOR_TYPES = [
  { label: '3rd party', value: 'third_party' },
  { label: 'In-house', value: 'inhouse' },
]

export const ITEM_CATEGORY_SCOPES = [
  { label: 'Service', value: 'service' },
  { label: 'Tangible', value: 'tangible' },
  { label: 'Mud chemical', value: 'mud_chemical' },
  { label: 'Cement additive', value: 'cement_additive' },
]

/** Common hole sections offered as suggestions when entering section-wise rates. */
export const HOLE_SECTIONS = [
  '36"',
  '26"',
  '17-1/2"',
  '12-1/4"',
  '8-1/2"',
  '6"',
]
