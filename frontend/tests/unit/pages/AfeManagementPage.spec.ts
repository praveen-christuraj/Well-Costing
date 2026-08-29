import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

/**
 * Page-level test for AFE Management: the AFE tab carries the common template
 * (Import / XLSX / CSV / Print), the AFE Cost Estimation tab lists every AFE
 * with its compiled total and prints one complete AFE, and the Deleted Entries
 * tab restores or permanently deletes.
 */

const rigs = [
  { id: 1, rig_code: 'RIG001', rig_name: 'Drilling Rig Alpha', display_name: 'RIG001 - Drilling Rig Alpha' },
]

const wells = [
  { id: 1, rig_id: 1, well_code: 'WELL001', well_name: 'Exploratory 1', config_status: 'configured', section_count: 1 },
]

const afeRows = [
  {
    id: 10,
    afe_code: 'AFE-001',
    afe_name: 'Surface section drilling',
    afe_type: 'Drilling',
    rig_id: 1,
    well_id: 1,
    remarks: null,
    status: 'draft',
    status_remarks: null,
    submitted_at: null,
    approved_at: null,
    rig_code: 'RIG001',
    rig_name: 'Drilling Rig Alpha',
    rig_display: 'RIG001 - Drilling Rig Alpha',
    well_code: 'WELL001',
    well_name: 'Exploratory 1',
    well_display: 'WELL001 - Exploratory 1',
    service_count: 2,
    consumable_count: 1,
    tangible_count: 1,
    estimated_total: '24800.00',
  },
  {
    id: 11,
    afe_code: 'AFE-002',
    afe_name: 'Completion of WELL001',
    afe_type: 'Completion',
    rig_id: 1,
    well_id: 1,
    remarks: null,
    status: 'approved',
    status_remarks: 'budget released',
    submitted_at: '2026-08-29T09:00:00Z',
    approved_at: '2026-08-29T10:00:00Z',
    rig_code: 'RIG001',
    rig_name: 'Drilling Rig Alpha',
    rig_display: 'RIG001 - Drilling Rig Alpha',
    well_code: 'WELL001',
    well_name: 'Exploratory 1',
    well_display: 'WELL001 - Exploratory 1',
    service_count: 0,
    consumable_count: 0,
    tangible_count: 0,
    estimated_total: '0.00',
  },
]

const deletedRows = [
  { ...afeRows[0], id: 12, afe_code: 'AFE-900', status: 'draft', is_deleted: true, deleted_at: '2026-08-28T09:00:00Z' },
]

const estimate = {
  afe: afeRows[0],
  well_configuration: {
    well_id: 1,
    well_code: 'WELL001',
    well_name: 'Exploratory 1',
    rig_code: 'RIG001',
    rig_name: 'Drilling Rig Alpha',
    status: 'active',
    config_status: 'configured',
    depth_unit: 'm',
    total_depth: '1500',
    total_days: '8.00',
    sections: [
      {
        id: 21,
        section_id: 1,
        section_code: 'SEC1',
        section_name: 'Surface Section',
        from_depth: '0',
        to_depth: '1500',
        remarks: null,
        total_days: '8.00',
        phases: [
          { id: 31, phase_id: 1, phase_code: 'PH1', phase_name: 'Drilling', days: '5.50', remarks: null },
          { id: 32, phase_id: 2, phase_code: 'PH2', phase_name: 'Casing', days: '2.50', remarks: null },
        ],
      },
    ],
  },
  services: [
    {
      id: 41,
      service_id: 5,
      service_code: 'SVC-0001',
      service_name: 'Directional Drilling',
      provider_type: 'Inhouse',
      charging_basis: 'Daily Rate',
      section_id: null,
      phase_id: null,
      per_service_amount: '0',
      effective_date: null,
      remarks: null,
      rates: [{ category: 'Operation', unit_rate: '1000' }, { category: 'Mobilization', unit_rate: '5000' }],
      charge_lines: [],
      section_rates: [],
      estimate: {
        amount: '13000.00',
        components: [
          { category: 'Operation', description: 'Operation — 8.0 planned day(s) @ 1000.00', quantity: '8.0', rate: '1000.00', unit: 'days', amount: '8000.00', section_label: null, phase_label: null },
          { category: 'Mobilization', description: 'Mobilization — charged once', quantity: '1', rate: '5000.00', unit: null, amount: '5000.00', section_label: null, phase_label: null },
        ],
        warnings: [],
      },
    },
  ],
  consumables: [
    {
      id: 51,
      item_kind: 'mud_chemical',
      item_id: 7,
      item_code: 'MC-0001',
      item_name: 'Bentonite',
      quantity: '10',
      captured_rate: '120.00',
      override_rate: null,
      uom: 'Sack',
      currency: 'USD',
      section_id: 1,
      phase_id: 1,
      remarks: null,
      estimate: {
        amount: '1200.00',
        components: [
          { category: 'Consumption', description: 'Bentonite — 10 Sack @ 120.00', quantity: '10', rate: '120.00', unit: 'Sack', amount: '1200.00', section_label: 'SEC1 — Surface Section', phase_label: 'PH1 — Drilling' },
        ],
        warnings: [],
      },
    },
  ],
  tangibles: [
    {
      id: 61,
      tangible_id: 9,
      tangible_code: 'TNG-0001',
      tangible_name: 'Casing 9-5/8',
      quantity: '2',
      captured_rate: '500.00',
      override_rate: '450',
      uom: 'm',
      currency: 'USD',
      remarks: null,
      estimate: {
        amount: '900.00',
        components: [
          { category: 'Override rate', description: 'Casing 9-5/8 — 2 m @ 450.00', quantity: '2', rate: '450.00', unit: 'm', amount: '900.00', section_label: null, phase_label: null },
        ],
        warnings: [],
      },
    },
  ],
  summary: [
    { group: 'Services', amount: '13000.00', line_count: 1 },
    { group: 'Consumables', amount: '1200.00', line_count: 1 },
    { group: 'Tangibles', amount: '900.00', line_count: 1 },
  ],
  by_section: [
    { section_id: 1, section_label: 'SEC1 — Surface Section', planned_days: '8.00', amount: '1200.00' },
    { section_id: null, section_label: 'Well-wide (no section)', planned_days: '0', amount: '13900.00' },
  ],
  grand_total: '15100.00',
  warnings: [],
}

type ApiMock = Record<'get' | 'post' | 'put' | 'delete' | 'download', ReturnType<typeof vi.fn>>

function makeApi(): ApiMock {
  return {
    get: vi.fn((path: string) => {
      if (path === '/rig-well/rigs/dropdown') return Promise.resolve(rigs)
      if (path === '/rig-well/wells') return Promise.resolve(wells)
      if (path.startsWith('/catalogue/services')) return Promise.resolve([{ id: 5, service_code: 'SVC-0001', service_name: 'Directional Drilling', provider_type: 'Inhouse' }])
      if (path.startsWith('/catalogue/mud-chemicals')) return Promise.resolve([{ id: 7, chemical_code: 'MC-0001', chemical_name: 'Bentonite', current_rate: '120.00', uom: 'Sack', currency: 'USD' }])
      if (path.startsWith('/catalogue/drill-bits')) return Promise.resolve([])
      if (path.startsWith('/catalogue/tangibles')) return Promise.resolve([{ id: 9, tangible_code: 'TNG-0001', tangible_name: 'Casing 9-5/8', final_cost: '500.00', uom: 'm', currency: 'USD', tangible_scope: 'Drilling', category: 'Casing' }])
      if (path === '/afe/afes') return Promise.resolve(afeRows)
      if (path === '/afe/estimates') return Promise.resolve(afeRows)
      if (path === '/afe/afes/deleted') return Promise.resolve(deletedRows)
      if (path === '/afe/estimates/10') return Promise.resolve(estimate)
      return Promise.resolve([])
    }),
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
    download: vi.fn().mockResolvedValue(new Blob()),
  }
}

async function mountPage() {
  vi.resetModules()
  const api = makeApi()
  vi.stubGlobal('definePageMeta', vi.fn())
  vi.stubGlobal('useApi', () => api)

  const component = (await import('~/pages/afe-management/index.vue')).default
  const wrapper = mount(component, { attachTo: document.body })
  await flushPromises()
  return { wrapper, api }
}

function findTab(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.tabs__item').find(tab => tab.text().includes(label))
}

function rowButton(wrapper: ReturnType<typeof mount>, text: string, label: string) {
  const row = wrapper.findAll('tbody tr').find(candidate => candidate.text().includes(text))
  return row?.findAll('button').find(button => button.text().includes(label))
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('AFE Management — common template and tabs', () => {
  it('renders the three navigation tabs with the shared tab strip', async () => {
    const { wrapper } = await mountPage()
    const labels = wrapper.findAll('.tabs__item').map(tab => tab.text().trim())
    expect(labels).toEqual(['AFE', 'AFE Cost Estimation', 'Deleted Entries'])
    expect(findTab(wrapper, 'Deleted Entries')?.classes()).toContain('tabs__item--danger')
    wrapper.unmount()
  })

  it('carries Import, XLSX, CSV and Print on the AFE entry tab', async () => {
    const { wrapper } = await mountPage()
    const toolbar = wrapper.find('[data-testid="excel-grid"]')
    expect(toolbar.exists()).toBe(true)
    const labels = wrapper.findAll('button').map(button => button.text())
    for (const expected of ['Import', 'XLSX', 'CSV', 'Print', 'Save All']) {
      expect(labels.some(label => label.includes(expected))).toBe(true)
    }
    wrapper.unmount()
  })
})

describe('AFE Management — cost estimation tab', () => {
  it('lists every AFE with its status, line counts and compiled total', async () => {
    const { wrapper } = await mountPage()
    await findTab(wrapper, 'AFE Cost Estimation')?.trigger('click')
    await flushPromises()

    const text = wrapper.find('.afe-table').text()
    expect(text).toContain('AFE-001')
    expect(text).toContain('Surface section drilling')
    expect(text).toContain('Draft')
    expect(text).toContain('2 / 1 / 1')
    expect(text).toContain('24,800.00')
    expect(text).toContain('Approved')
    wrapper.unmount()
  })

  it('opens the cost estimation dialog from its row', async () => {
    const { wrapper, api } = await mountPage()
    await findTab(wrapper, 'AFE Cost Estimation')?.trigger('click')
    await flushPromises()

    await rowButton(wrapper, 'AFE-001', 'Cost Estimate')?.trigger('click')
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('/afe/estimates/10')
    wrapper.unmount()
  })

  it('prints one complete AFE — well configuration plus the three cost groups', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { wrapper, api } = await mountPage()
    await findTab(wrapper, 'AFE Cost Estimation')?.trigger('click')
    await flushPromises()

    await rowButton(wrapper, 'AFE-001', 'Print')?.trigger('click')
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('/afe/estimates/10')
    expect(print).toHaveBeenCalledTimes(1)

    const sheets = wrapper.findAll('.print-sheet')
    expect(sheets).toHaveLength(1)
    const sheet = sheets[0]
    expect(sheet?.text()).toContain('AFE-001 — Surface section drilling')
    // Well configuration metadata
    expect(sheet?.text()).toContain('SEC1 — Surface Section')
    expect(sheet?.text()).toContain('PH1 — Drilling')
    expect(sheet?.text()).toContain('1500 m')
    // The three cost groups and the compiled total
    expect(sheet?.text()).toContain('Directional Drilling')
    expect(sheet?.text()).toContain('Bentonite')
    expect(sheet?.text()).toContain('Casing 9-5/8')
    expect(sheet?.text()).toContain('Total AFE cost estimate')
    expect(sheet?.text()).toContain('15,100.00')
    // The list sheet is not part of the single-AFE print output.
    expect(sheet?.text()).not.toContain('AFE-002')
    wrapper.unmount()
  })

  it('goes back to the list sheet once printing finishes', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { wrapper } = await mountPage()
    await findTab(wrapper, 'AFE Cost Estimation')?.trigger('click')
    await flushPromises()
    await rowButton(wrapper, 'AFE-001', 'Print')?.trigger('click')
    await flushPromises()

    window.dispatchEvent(new Event('afterprint'))
    await flushPromises()

    const sheet = wrapper.findAll('.print-sheet')[0]
    expect(sheet?.text()).toContain('2 AFE(s)')
    expect(print).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('exports the estimate list in both formats', async () => {
    const { wrapper, api } = await mountPage()
    await findTab(wrapper, 'AFE Cost Estimation')?.trigger('click')
    await flushPromises()

    const buttons = wrapper.findAll('.afe-toolbar__actions button')
    await buttons.find(button => button.text().includes('XLSX'))?.trigger('click')
    await buttons.find(button => button.text().includes('CSV'))?.trigger('click')
    await flushPromises()

    expect(api.download).toHaveBeenCalledWith('/afe/estimates/export?format=xlsx')
    expect(api.download).toHaveBeenCalledWith('/afe/estimates/export?format=csv')
    wrapper.unmount()
  })
})

describe('AFE Management — deleted entries', () => {
  it('restores and permanently deletes from the trash', async () => {
    const { wrapper, api } = await mountPage()
    await findTab(wrapper, 'Deleted Entries')?.trigger('click')
    await flushPromises()

    expect(wrapper.find('.trash-table').text()).toContain('AFE-900')

    await rowButton(wrapper, 'AFE-900', 'Restore')?.trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/afe/afes/12/restore', {})

    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await rowButton(wrapper, 'AFE-900', 'Delete')?.trigger('click')
    await flushPromises()
    expect(api.delete).toHaveBeenCalledWith('/afe/afes/12/permanent')
    wrapper.unmount()
  })
})
