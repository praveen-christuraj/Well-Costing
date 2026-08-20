import type { ApiClient } from '~/services/apiClient'
import type { BulkValidationResult, PageResponse } from '~/types/masterData'
import type {
  ItemPriceRecord,
  PurchaseOrderRecord,
  RateRevisionRecord,
  ServiceOrderRecord,
} from '~/types/procurement'

export type QueryValue = string | number | boolean | null | undefined

/** Build a query string, dropping empty filter values so URLs stay readable. */
export function buildQuery(params: Record<string, QueryValue>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    query.set(key, String(value))
  }
  return query.toString()
}

/** Typed CRUD + bulk client for one procurement resource. */
export class ProcurementResource<TRecord> {
  constructor(
    private readonly api: ApiClient,
    private readonly path: string,
  ) {}

  list(params: Record<string, QueryValue> = {}): Promise<PageResponse<TRecord>> {
    return this.api.get(`/procurement/${this.path}?${buildQuery(params)}`)
  }

  create(payload: Record<string, unknown>): Promise<TRecord> {
    return this.api.post(`/procurement/${this.path}`, payload)
  }

  update(id: string, payload: Record<string, unknown>): Promise<TRecord> {
    return this.api.patch(`/procurement/${this.path}/${id}`, payload)
  }

  validate(rows: Record<string, unknown>[]): Promise<BulkValidationResult> {
    return this.api.post(`/procurement/${this.path}/bulk/validate`, { rows })
  }

  bulkCreate(rows: Record<string, unknown>[]): Promise<TRecord[]> {
    return this.api.post(`/procurement/${this.path}/bulk/create`, { rows })
  }

  bulkUpdate(rows: Record<string, unknown>[]): Promise<TRecord[]> {
    return this.api.patch(`/procurement/${this.path}/bulk/update`, { rows })
  }

  /** Deactivate by default; pass hard to permanently remove the record. */
  remove(id: string, hard = false): Promise<undefined> {
    return this.api.delete(`/procurement/${this.path}/${id}${hard ? '?hard=true' : ''}`)
  }
}

/** Supersede a master rate rather than overwrite it. */
export type ItemPriceRevision = {
  unit_price: string
  effective_from: string
  change_reason: string
  effective_to?: string | null
  vendor_id?: string | null
  currency_id?: string | null
  unit_id?: string | null
  description?: string | null
} & Record<string, unknown>

export class ProcurementApi {
  readonly serviceOrders: ProcurementResource<ServiceOrderRecord>
  readonly purchaseOrders: ProcurementResource<PurchaseOrderRecord>
  readonly itemPrices: ProcurementResource<ItemPriceRecord>

  constructor(private readonly api: ApiClient) {
    this.serviceOrders = new ProcurementResource(api, 'service-orders')
    this.purchaseOrders = new ProcurementResource(api, 'purchase-orders')
    this.itemPrices = new ProcurementResource(api, 'item-prices')
  }

  /**
   * Close the current master rate and open its next revision. Wells that already
   * copied the old rate into their rate book keep it until completion.
   */
  reviseItemPrice(id: string, payload: ItemPriceRevision): Promise<ItemPriceRecord> {
    return this.api.post(`/procurement/item-prices/${id}/revise`, payload)
  }

  /** The master rate change log: who changed which rate, when, and why. */
  rateRevisions(params: Record<string, QueryValue> = {}): Promise<PageResponse<RateRevisionRecord>> {
    return this.api.get(`/procurement/rate-revisions?${buildQuery(params)}`)
  }
}
