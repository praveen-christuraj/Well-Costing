import { describe, expect, it, vi } from 'vitest'
import { WellCostingApi } from '~/services/wellCosting'
import type { ApiClient } from '~/services/apiClient'

function stubClient() {
  return {
    get: vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 50, total: 0, pages: 0 }),
    post: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
  } as unknown as ApiClient
}

const WELL = 'well-1'

describe('WellCostingApi rate book', () => {
  it('scopes every rate-book read to one well', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)

    await api.listServices(WELL, { status: 'locked', page: 2 })
    await api.listTangibles(WELL)

    expect(client.get).toHaveBeenNthCalledWith(
      1,
      '/wells/well-1/rate-book/services?status=locked&page=2',
    )
    expect(client.get).toHaveBeenNthCalledWith(2, '/wells/well-1/rate-book/tangibles?')
  })

  it('offers the master catalogue filtered by search', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)

    await api.availableServices(WELL, 'mwd')
    await api.availableTangibles(WELL)

    expect(client.get).toHaveBeenNthCalledWith(
      1,
      '/wells/well-1/rate-book/available-services?search=mwd',
    )
    expect(client.get).toHaveBeenNthCalledWith(
      2,
      '/wells/well-1/rate-book/available-tangibles?',
    )
  })

  it('adds a service at the rate negotiated for the well', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)
    const payload = { service_id: 's-1', operating_rate: '12500' }

    await api.addService(WELL, payload)

    expect(client.post).toHaveBeenCalledWith('/wells/well-1/rate-book/services', payload)
  })

  it('sends the change reason when revising a well rate', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)

    await api.updateTangible(WELL, 'rate-9', { unit_rate: '51000', change_reason: 'Amendment 2' })

    expect(client.patch).toHaveBeenCalledWith('/wells/well-1/rate-book/tangibles/rate-9', {
      unit_rate: '51000',
      change_reason: 'Amendment 2',
    })
  })

  it('locks the rate book at AFE issue', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)

    await api.lock(WELL, { reference: 'AFE-2026-001' })

    expect(client.post).toHaveBeenCalledWith('/wells/well-1/rate-book/lock', {
      reference: 'AFE-2026-001',
    })
  })

  it('passes a removal reason as a query parameter', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)

    await api.removeService(WELL, 'rate-3', 'Not required')

    expect(client.delete).toHaveBeenCalledWith(
      '/wells/well-1/rate-book/services/rate-3?reason=Not+required',
    )
  })
})

describe('WellCostingApi out-of-AFE register', () => {
  it('walks an entry through submit and approve', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)

    await api.submitUnplanned(WELL, 'ooa-1')
    await api.approveUnplanned(WELL, 'ooa-1', { decision_note: 'Approved' })

    expect(client.post).toHaveBeenNthCalledWith(1, '/wells/well-1/unplanned-items/ooa-1/submit', {})
    expect(client.post).toHaveBeenNthCalledWith(2, '/wells/well-1/unplanned-items/ooa-1/approve', {
      decision_note: 'Approved',
    })
  })

  it('filters the register by status', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)

    await api.listUnplanned(WELL, { status: 'submitted' })

    expect(client.get).toHaveBeenCalledWith('/wells/well-1/unplanned-items?status=submitted')
  })

  it('reads the AFE versus out-of-AFE position', async () => {
    const client = stubClient()
    const api = new WellCostingApi(client)

    await api.costExposure(WELL)

    expect(client.get).toHaveBeenCalledWith('/wells/well-1/cost-exposure')
  })
})
