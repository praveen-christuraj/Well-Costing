export interface EstimateItem {
  id: string; estimate_version_id: string; line_number: number; catalog_item_id: string
  catalog_item_code: string | null; catalog_item_name: string | null; item_type: string | null; cost_code: string | null
  vendor_id: string | null; vendor_code: string | null; rate_id: string | null
  rate_amount: string | null; quantity: string; unit_id: string; unit_code: string | null
  notes: string | null; base_cost: string | null; contingency_cost: string | null
  escalation_cost: string | null; total_cost: string | null
}
export interface EstimateAssumption { id: string; cost_category_id: string | null; contingency_percent: string | null; escalation_percent: string | null; notes: string | null }
export interface EstimateVersion { id: string; estimate_id: string; version_number: number; status: string; notes: string | null; items: EstimateItem[]; assumptions: EstimateAssumption[] }
/** Relationship-derived fields degrade to null when the referenced record was hard-deleted. */
export interface Estimate { id: string; afe_id: string; afe_code: string | null; well_code: string | null; project_code: string | null; code: string; title: string; currency_id: string; currency_code: string | null; current_version_number: number; is_active: boolean; deleted_at: string | null; versions: EstimateVersion[] }
