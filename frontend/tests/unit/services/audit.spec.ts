import { AuditApi } from '~/services/audit'

describe('AuditApi exports', () => {
  it('exports the complete filtered audit log', async () => {
    const download = vi.fn().mockResolvedValue(new Blob())
    const api = new AuditApi({ download } as never)

    await api.export({ action: 'save_rates', entity_type: 'afe_cost_estimate' })

    expect(download).toHaveBeenCalledWith(
      '/audit-logs/export?action=save_rates&entity_type=afe_cost_estimate',
    )
  })

  it('loads every page for printing', async () => {
    const get = vi.fn()
      .mockResolvedValueOnce({ items: [{ id: '1' }], pages: 2 })
      .mockResolvedValueOnce({ items: [{ id: '2' }], pages: 2 })
    const api = new AuditApi({ get } as never)

    const rows = await api.listAll({ entity_type: 'daily_cost_entry' })

    expect(rows.map(row => row.id)).toEqual(['1', '2'])
    expect(get).toHaveBeenNthCalledWith(
      1,
      '/audit-logs?page=1&page_size=500&entity_type=daily_cost_entry',
    )
    expect(get).toHaveBeenNthCalledWith(
      2,
      '/audit-logs?page=2&page_size=500&entity_type=daily_cost_entry',
    )
  })
})
