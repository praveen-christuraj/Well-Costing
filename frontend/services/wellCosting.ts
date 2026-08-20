/**
 * Client for the well rate book and the out-of-AFE register.
 *
 * Every call is scoped to one well, mirroring the API: a rate only exists in
 * the context of the well that negotiated it, which is what keeps concurrently
 * drilling rigs independent of central rate revisions.
 */
import type { ApiClient } from '~/services/apiClient'
import { buildQuery, type QueryValue } from '~/services/procurement'
import type { PageResponse } from '~/types/masterData'
import type {
  AvailableServiceRecord,
  AvailableTangibleRecord,
  RateBookLockResult,
  WellCostExposure,
  WellRateRevisionRecord,
  WellServiceRateRecord,
  WellTangibleRateRecord,
  WellUnplannedItemRecord,
} from '~/types/wellCosting'

export class WellCostingApi {
  constructor(private readonly api: ApiClient) {}

  private base(wellId: string): string {
    return `/wells/${wellId}`
  }

  /** Master services, flagged with whether this well already prices them. */
  availableServices(wellId: string, search?: string): Promise<AvailableServiceRecord[]> {
    return this.api.get(`${this.base(wellId)}/rate-book/available-services?${buildQuery({ search })}`)
  }

  /** Master tangibles with the master rate that would be copied into the well. */
  availableTangibles(wellId: string, search?: string): Promise<AvailableTangibleRecord[]> {
    return this.api.get(`${this.base(wellId)}/rate-book/available-tangibles?${buildQuery({ search })}`)
  }

  listServices(
    wellId: string,
    params: Record<string, QueryValue> = {},
  ): Promise<PageResponse<WellServiceRateRecord>> {
    return this.api.get(`${this.base(wellId)}/rate-book/services?${buildQuery(params)}`)
  }

  /** Add a service at the rate negotiated for this well; there is no master rate. */
  addService(wellId: string, payload: Record<string, unknown>): Promise<WellServiceRateRecord> {
    return this.api.post(`${this.base(wellId)}/rate-book/services`, payload)
  }

  /** Revise before the AFE locks the book; `change_reason` is required. */
  updateService(
    wellId: string,
    rateId: string,
    payload: Record<string, unknown>,
  ): Promise<WellServiceRateRecord> {
    return this.api.patch(`${this.base(wellId)}/rate-book/services/${rateId}`, payload)
  }

  removeService(wellId: string, rateId: string, reason?: string): Promise<undefined> {
    return this.api.delete(
      `${this.base(wellId)}/rate-book/services/${rateId}?${buildQuery({ reason })}`,
    )
  }

  listTangibles(
    wellId: string,
    params: Record<string, QueryValue> = {},
  ): Promise<PageResponse<WellTangibleRateRecord>> {
    return this.api.get(`${this.base(wellId)}/rate-book/tangibles?${buildQuery(params)}`)
  }

  /** Copy the current master rate into the well, or override it with a reason. */
  addTangible(wellId: string, payload: Record<string, unknown>): Promise<WellTangibleRateRecord> {
    return this.api.post(`${this.base(wellId)}/rate-book/tangibles`, payload)
  }

  updateTangible(
    wellId: string,
    rateId: string,
    payload: Record<string, unknown>,
  ): Promise<WellTangibleRateRecord> {
    return this.api.patch(`${this.base(wellId)}/rate-book/tangibles/${rateId}`, payload)
  }

  removeTangible(wellId: string, rateId: string, reason?: string): Promise<undefined> {
    return this.api.delete(
      `${this.base(wellId)}/rate-book/tangibles/${rateId}?${buildQuery({ reason })}`,
    )
  }

  /** Freeze the well's rates, typically when the AFE baseline is issued. */
  lock(wellId: string, payload: Record<string, unknown> = {}): Promise<RateBookLockResult> {
    return this.api.post(`${this.base(wellId)}/rate-book/lock`, payload)
  }

  revisions(
    wellId: string,
    params: Record<string, QueryValue> = {},
  ): Promise<PageResponse<WellRateRevisionRecord>> {
    return this.api.get(`${this.base(wellId)}/rate-book/revisions?${buildQuery(params)}`)
  }

  listUnplanned(
    wellId: string,
    params: Record<string, QueryValue> = {},
  ): Promise<PageResponse<WellUnplannedItemRecord>> {
    return this.api.get(`${this.base(wellId)}/unplanned-items?${buildQuery(params)}`)
  }

  /** Record a charge incurred outside the approved AFE and the well plan. */
  createUnplanned(
    wellId: string,
    payload: Record<string, unknown>,
  ): Promise<WellUnplannedItemRecord> {
    return this.api.post(`${this.base(wellId)}/unplanned-items`, payload)
  }

  updateUnplanned(
    wellId: string,
    itemId: string,
    payload: Record<string, unknown>,
  ): Promise<WellUnplannedItemRecord> {
    return this.api.patch(`${this.base(wellId)}/unplanned-items/${itemId}`, payload)
  }

  submitUnplanned(wellId: string, itemId: string): Promise<WellUnplannedItemRecord> {
    return this.api.post(`${this.base(wellId)}/unplanned-items/${itemId}/submit`, {})
  }

  /** Approve the deviation and price it into the well rate book. */
  approveUnplanned(
    wellId: string,
    itemId: string,
    payload: Record<string, unknown> = {},
  ): Promise<WellUnplannedItemRecord> {
    return this.api.post(`${this.base(wellId)}/unplanned-items/${itemId}/approve`, payload)
  }

  rejectUnplanned(
    wellId: string,
    itemId: string,
    payload: Record<string, unknown> = {},
  ): Promise<WellUnplannedItemRecord> {
    return this.api.post(`${this.base(wellId)}/unplanned-items/${itemId}/reject`, payload)
  }

  cancelUnplanned(
    wellId: string,
    itemId: string,
    payload: Record<string, unknown> = {},
  ): Promise<WellUnplannedItemRecord> {
    return this.api.post(`${this.base(wellId)}/unplanned-items/${itemId}/cancel`, payload)
  }

  /** Approved AFE, approved out-of-AFE spend, pending requests, and variance. */
  costExposure(wellId: string): Promise<WellCostExposure> {
    return this.api.get(`${this.base(wellId)}/cost-exposure`)
  }
}
