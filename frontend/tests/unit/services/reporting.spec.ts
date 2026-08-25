import { ReportingApi } from '~/services/reporting'

describe('ReportingApi', () => {
  it('generates and exports the selected active-source report with filters', async () => {
    const get = vi.fn().mockResolvedValue({ rows: [] })
    const download = vi.fn().mockResolvedValue(new Blob())
    const api = new ReportingApi({ get, download } as never)
    const filters = {
      report_type: 'daily_cost' as const,
      well_id: 'well-1',
      date_from: '2026-08-01',
      date_to: '2026-08-25',
    }

    await api.generate(filters)
    await api.export(filters)

    expect(get).toHaveBeenCalledWith(
      '/reports/generate?report_type=daily_cost&well_id=well-1&date_from=2026-08-01&date_to=2026-08-25',
    )
    expect(download).toHaveBeenCalledWith(
      '/reports/export?report_type=daily_cost&well_id=well-1&date_from=2026-08-01&date_to=2026-08-25',
    )
  })
})
