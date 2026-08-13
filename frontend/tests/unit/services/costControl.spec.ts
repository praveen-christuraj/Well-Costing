import type { ApiClient } from '~/services/apiClient'
import { CostControlApi } from '~/services/costControl'
import type { CostControlLineInput } from '~/types/costControl'

const line: CostControlLineInput = {
  transaction_date: '2026-08-13', source_document_type: 'field_ticket', source_document_reference: 'FT-001',
  external_transaction_id: null, cost_code: 'CC-001', vendor_code: null, description: 'Test cost',
  quantity: null, unit_code: null, currency_code: 'USD', amount: '10.0000', correction_kind: 'original',
  reverses_transaction_id: null,
}

describe('CostControlApi', () => {
  it('preserves the selected cost state in bulk validation', async () => {
    const post = vi.fn().mockResolvedValue({ id: 'batch-1' })
    const client = { post } as unknown as ApiClient
    const api = new CostControlApi(client)

    await api.validate('version-1', 'forecast', [line])

    expect(post).toHaveBeenCalledWith('/cost-control/batches/validate', {
      estimate_version_id: 'version-1', cost_state: 'forecast', rows: [line],
    })
  })
})
