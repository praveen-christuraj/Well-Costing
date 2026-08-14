import { describe, expect, it, vi } from 'vitest'
import { ProcurementApi, ProcurementResource, buildQuery } from '~/services/procurement'
import type { ApiClient } from '~/services/apiClient'

function stubClient() {
  return {
    get: vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 25, total: 0, pages: 0 }),
    post: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
  } as unknown as ApiClient
}

describe('buildQuery', () => {
  it('serialises provided values', () => {
    expect(buildQuery({ page: 2, page_size: 25 })).toBe('page=2&page_size=25')
  })

  it('drops null, undefined, and empty values so filters stay optional', () => {
    expect(buildQuery({ page: 1, vendor_id: null, status: undefined, search: '' })).toBe('page=1')
  })

  it('keeps boolean filters', () => {
    expect(buildQuery({ is_active: false })).toBe('is_active=false')
  })
})

describe('ProcurementResource', () => {
  it('requests a filtered page from the resource path', async () => {
    const client = stubClient()
    const resource = new ProcurementResource(client, 'service-rates')

    await resource.list({ page: 3, vendor_id: 'v-1', hole_section: null })

    expect(client.get).toHaveBeenCalledWith('/procurement/service-rates?page=3&vendor_id=v-1')
  })

  it('posts bulk validation and creation payloads', async () => {
    const client = stubClient()
    const resource = new ProcurementResource(client, 'item-prices')
    const rows = [{ unit_price: '10' }]

    await resource.validate(rows)
    await resource.bulkCreate(rows)

    expect(client.post).toHaveBeenNthCalledWith(1, '/procurement/item-prices/bulk/validate', { rows })
    expect(client.post).toHaveBeenNthCalledWith(2, '/procurement/item-prices/bulk/create', { rows })
  })

  it('deactivates by default and hard deletes on request', async () => {
    const client = stubClient()
    const resource = new ProcurementResource(client, 'service-orders')

    await resource.remove('abc')
    await resource.remove('abc', true)

    expect(client.delete).toHaveBeenNthCalledWith(1, '/procurement/service-orders/abc')
    expect(client.delete).toHaveBeenNthCalledWith(2, '/procurement/service-orders/abc?hard=true')
  })
})

describe('ProcurementApi', () => {
  it('exposes one resource per procurement entity', async () => {
    const client = stubClient()
    const api = new ProcurementApi(client)

    await api.serviceOrders.list()
    await api.purchaseOrders.list()
    await api.serviceRates.list()
    await api.itemPrices.list()

    expect(client.get).toHaveBeenCalledWith('/procurement/service-orders?')
    expect(client.get).toHaveBeenCalledWith('/procurement/purchase-orders?')
    expect(client.get).toHaveBeenCalledWith('/procurement/service-rates?')
    expect(client.get).toHaveBeenCalledWith('/procurement/item-prices?')
  })
})
