import type { ApiClient } from '~/services/apiClient'
import { buildQuery, type QueryValue } from '~/services/procurement'
import type {
  DropdownBindingWrite,
  DropdownRegistry,
  DropdownSlot,
  ReferenceOptions,
} from '~/types/reference'

/** Client for the configurable dropdown registry. */
export class ReferenceApi {
  constructor(private readonly api: ApiClient) {}

  /** Every slot, source, and current binding — the super-admin console view. */
  registry(module?: string): Promise<DropdownRegistry> {
    const query = module ? `?module=${encodeURIComponent(module)}` : ''
    return this.api.get(`/reference/registry${query}`)
  }

  /** Row count behind each source, so an empty binding is visible at a glance. */
  usage(): Promise<Record<string, number>> {
    return this.api.get('/reference/registry/usage')
  }

  slot(slotCode: string): Promise<DropdownSlot> {
    return this.api.get(`/reference/slots/${slotCode}`)
  }

  /** Point a dropdown at another registered source. Super administrators only. */
  bind(slotCode: string, payload: DropdownBindingWrite): Promise<DropdownSlot> {
    return this.api.put(`/reference/slots/${slotCode}`, payload as unknown as Record<string, unknown>)
  }

  /** Restore the source declared in code. */
  reset(slotCode: string): Promise<DropdownSlot> {
    return this.api.deleteJson<DropdownSlot>(`/reference/slots/${slotCode}`)
  }

  /** Resolved options for one dropdown. */
  options(
    slotCode: string,
    params: Record<string, QueryValue> = {},
  ): Promise<ReferenceOptions> {
    return this.api.get(`/reference/options/${slotCode}?${buildQuery(params)}`)
  }
}
