import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Select from 'primevue/select'

/**
 * Page-level test for Daily Costs: the sheet is opened by rig → well → cost
 * date, the money on screen comes from the server preview (never from the
 * browser), and the day is saved as a draft, then submitted. The common
 * template (Import / XLSX / CSV / Print / Deleted Entries) is present.
 */

const rigs = [
  { id: 1, rig_code: 'RIG001', rig_name: 'Drilling Rig Alpha', display_name: 'RIG001 - Drilling Rig Alpha' },
]
const wells = [
  { id: 1, rig_id: 1, well_code: 'WELL001', well_name: 'Exploratory 1', status: 'active' },
  { id: 2, rig_id: 1, well_code: 'WELL002', well_name: 'Development 2', status: 'active' },
]
const services = [
  { id: 31, service_code: 'SVC-0001', service_name: 'Directional Drilling', provider_type: '3rd Party' },
  { id: 32, service_code: 'SVC-0002', service_name: 'Cementing Job', provider_type: 'Inhouse' },
]
const chemicals = [
  { id: 41, chemical_code: 'MC-0001', chemical_name: 'Bentonite', current_rate: '50.00', uom: 'Sack', currency: 'USD' },
]
const bits = [
  { id: 51, bit_code: 'DB-0001', bit_name: '12-1/4 PDC', final_cost: '120.00', uom: 'Each', currency: 'USD' },
]
const tangibles = [
  { id: 61, tangible_code: 'TNG-0001', tangible_name: 'Casing 9-5/8', final_cost: '500.00', uom: 'Joint', currency: 'USD' },
]

const context = {
  well_id: 1,
  well_code: 'WELL001',
  well_name: 'Exploratory 1',
  rig_id: 1,
  rig_code: 'RIG001',
  rig_name: 'Drilling Rig Alpha',
  depth_unit: 'm',
  well_configuration: {
    depth_unit: 'm',
    total_depth: '3000',
    total_days: '12',
    sections: [
      {
        section_id: 11,
        section_code: 'SEC1',
        section_name: 'Surface Section',
        from_depth: '0',
        to_depth: '1500',
        phases: [{ phase_id: 21, phase_code: 'PH1', phase_name: 'Drilling', days: '5.5' }],
      },
    ],
  },
  afes: [{ id: 71, afe_code: 'AFE-001', afe_name: 'Surface section drilling', afe_type: 'Drilling', status: 'submitted' }],
  sub_activities: [
    { id: 81, sub_activity_code: 'RIH-01', sub_activity_name: 'Run in hole with tubing', activity_id: 91, activity_code: 'DRL' },
  ],
  rate_card: [
    {
      service_id: 31,
      afe_line_id: 101,
      service_code: 'SVC-0001',
      service_name: 'Directional Drilling',
      provider_type: '3rd Party',
      charging_basis: 'Daily Rate',
      per_service_amount: '0',
      section_id: null,
      phase_id: null,
      rates: [
        { category: 'Operation', unit_rate: '1000.00' },
        { category: 'Mobilization', unit_rate: '5000.00' },
      ],
      section_rates: [],
    },
  ],
  afe_id: 71,
  fuel_rate: '1.20',
  afe_estimated_total: '73000.00',
  warnings: [],
}

const emptyDay = null

function savedDay(status: 'draft' | 'submitted' = 'draft') {
  return {
    entry: {
      id: 7,
      daily_cost_code: 'WELL001/20260801',
      rig_id: 1,
      well_id: 1,
      cost_date: '2026-08-01',
      afe_id: 71,
      afe_code: 'AFE-001',
      remarks: null,
      status,
      submitted_at: status === 'submitted' ? '2026-08-01T18:00:00Z' : null,
      reconciliation_status: 'pending',
      reconciliation_ref: null,
      reconciled_at: null,
      is_deleted: false,
      deleted_at: null,
      created_at: null,
      updated_at: null,
      rig_code: 'RIG001',
      rig_name: 'Drilling Rig Alpha',
      rig_display: 'RIG001 - Drilling Rig Alpha',
      well_code: 'WELL001',
      well_name: 'Exploratory 1',
      well_display: 'WELL001 - Exploratory 1',
      service_count: 1,
      consumable_count: 0,
      tangible_count: 0,
      service_total: '500.00',
      consumable_total: '0',
      tangible_total: '0',
      total_cost: '500.00',
    },
    well_configuration: context.well_configuration,
    services: [
      {
        id: 901,
        service_id: 31,
        service_code: 'SVC-0001',
        service_name: 'Directional Drilling',
        provider_type: '3rd Party',
        afe_line_id: 101,
        charging_basis: 'Daily Rate',
        charge_category: 'Operation',
        section_id: 11,
        phase_id: 21,
        sub_activity_id: 81,
        sub_activity_display: 'RIH-01 - Run in hole with tubing (DRL)',
        quantity: '12.0000',
        quantity_unit: 'hours',
        captured_rate: '1000.00',
        override_rate: null,
        amount: '500.00',
        remarks: null,
      },
    ],
    consumables: [],
    tangibles: [],
    summary: [
      { group: 'Services', amount: '500.00' },
      { group: 'Consumables', amount: '0' },
      { group: 'Tangibles', amount: '0' },
      { group: 'Total', amount: '500.00' },
    ],
    grand_total: '500.00',
    warnings: [],
  }
}

const preview = {
  services: [{ line_id: null, code: 'SVC-0001', name: 'Directional Drilling', amount: '500.00', warnings: [] }],
  consumables: [],
  tangibles: [],
  summary: [
    { group: 'Services', amount: '500.00' },
    { group: 'Consumables', amount: '0' },
    { group: 'Tangibles', amount: '0' },
    { group: 'Total', amount: '500.00' },
  ],
  grand_total: '500.00',
  warnings: ['SVC-0001: Mobilization is a one-time charge — the entered hours/days are not multiplied'],
}

type ApiMock = Record<'get' | 'post' | 'put' | 'delete' | 'download', ReturnType<typeof vi.fn>>

function makeApi(day: unknown = emptyDay): ApiMock {
  return {
    get: vi.fn((path: string) => {
      if (path === '/rig-well/rigs/dropdown') return Promise.resolve(rigs)
      if (path === '/rig-well/wells') return Promise.resolve(wells)
      if (path === '/catalogue/services') return Promise.resolve(services)
      if (path === '/catalogue/mud-chemicals') return Promise.resolve(chemicals)
      if (path === '/catalogue/drill-bits') return Promise.resolve(bits)
      if (path === '/catalogue/tangibles') return Promise.resolve(tangibles)
      if (path.startsWith('/daily-cost/context')) return Promise.resolve(context)
      if (path.startsWith('/daily-cost/entries/for-date')) return Promise.resolve(day)
      if (path.startsWith('/daily-cost/entries/deleted')) return Promise.resolve([])
      return Promise.resolve([])
    }),
    post: vi.fn((path: string) => {
      if (path === '/daily-cost/preview') return Promise.resolve(preview)
      if (path === '/daily-cost/entries') return Promise.resolve(savedDay())
      return Promise.resolve({ id: 7, status: 'submitted' })
    }),
    put: vi.fn(() => Promise.resolve(savedDay())),
    delete: vi.fn(() => Promise.resolve(undefined)),
    download: vi.fn(() => Promise.resolve(new Blob())),
  }
}

async function mountPage(day: unknown = emptyDay) {
  vi.resetModules()
  const api = makeApi(day)
  vi.stubGlobal('definePageMeta', vi.fn())
  vi.stubGlobal('useApi', () => api)

  const component = (await import('~/pages/daily-costs/index.vue')).default
  const wrapper = mount(component, { attachTo: document.body })
  await flushPromises()
  return { wrapper, api }
}

function contextSelects(wrapper: ReturnType<typeof mount>) {
  return wrapper.find('.context-card').findAllComponents(Select)
}

/** Pick the rig and the well — the sheet opens for today's date. */
async function pickContext(wrapper: ReturnType<typeof mount>) {
  const [rigSelect] = contextSelects(wrapper)
  rigSelect.vm.$emit('update:model-value', 1)
  await flushPromises()
  const [, wellSelect] = contextSelects(wrapper)
  wellSelect.vm.$emit('update:model-value', 1)
  await flushPromises()
}

function buttonByLabel(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find(button => button.text().includes(label))
}

function findTab(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.toolbar__tab').find(tab => tab.text().includes(label))
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('Daily Costs — context and the day sheet', () => {
  it('asks for the rig, well and cost date before any entry', async () => {
    const { wrapper } = await mountPage()
    expect(wrapper.find('.context-card').exists()).toBe(true)
    expect(wrapper.find('[data-testid="daily-service-lines"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Select the rig, its well and the cost date')
    wrapper.unmount()
  })

  it('opens the day for the selected well and loads the well context', async () => {
    const { wrapper, api } = await mountPage()
    await pickContext(wrapper)

    const contextCall = (api.get as ReturnType<typeof vi.fn>).mock.calls
      .map(call => call[0] as string)
      .find(path => path.startsWith('/daily-cost/context'))
    expect(contextCall).toContain('well_id=1')
    expect(wrapper.find('[data-testid="daily-service-lines"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Daily cost for')
    expect(wrapper.text()).toContain('WELL001 - Exploratory 1')
    // The AFE budget the sheet reports what is left against.
    expect(wrapper.text()).toContain('73,000.00')
    wrapper.unmount()
  })

  it('shows the saved day, its totals and the fuel rate captured from the AFE', async () => {
    const { wrapper } = await mountPage(savedDay())
    await pickContext(wrapper)

    expect(wrapper.find('[data-testid="daily-cost-summary"]').text()).toContain('500.00')
    expect(wrapper.text()).toContain('WELL001/20260801')

    await findTab(wrapper, 'Consumables')?.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-consumable-lines"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('fuel takes its unit rate from the AFE')

    await findTab(wrapper, 'Tangibles')?.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-tangible-lines"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('The list comes from Master Data')
    wrapper.unmount()
  })

  it('prices an added line on the server instead of in the browser', async () => {
    const { wrapper, api } = await mountPage()
    await pickContext(wrapper)

    // Fake timers go on before the edit so the 600 ms debounce is ours to run.
    vi.useFakeTimers()
    await buttonByLabel(wrapper, 'Add service')?.trigger('click')
    await vi.advanceTimersByTimeAsync(700)
    vi.useRealTimers()
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-service-lines"]').text()).toContain('Select the service')

    const previewCall = (api.post as ReturnType<typeof vi.fn>).mock.calls
      .find(call => call[0] === '/daily-cost/preview')
    expect(previewCall).toBeTruthy()
    const body = previewCall?.[1] as { well_id: number, afe_id: number, services: unknown[] }
    expect(body.well_id).toBe(1)
    expect(body.afe_id).toBe(71)
    expect(body.services).toHaveLength(1)
    // The server-priced amount is what the row shows.
    expect(wrapper.find('[data-testid="daily-cost-summary"]').text()).toContain('500.00')
    wrapper.unmount()
  })

  it('saves the day as a draft, then submits it', async () => {
    const { wrapper, api } = await mountPage(savedDay())
    await pickContext(wrapper)

    await buttonByLabel(wrapper, 'Save draft')?.trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/daily-cost/entries/7', expect.objectContaining({
      services: expect.any(Array),
      consumables: expect.any(Array),
      tangibles: expect.any(Array),
    }))

    await buttonByLabel(wrapper, 'Submit')?.trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/daily-cost/entries/7/status', { action: 'submit' })
    wrapper.unmount()
  })

  it('locks a submitted day and offers to reopen it', async () => {
    const { wrapper } = await mountPage(savedDay('submitted'))
    await pickContext(wrapper)

    expect(wrapper.text()).toContain('This day is submitted')
    expect(buttonByLabel(wrapper, 'Reopen as draft')).toBeTruthy()
    expect(buttonByLabel(wrapper, 'Save draft')).toBeFalsy()
    wrapper.unmount()
  })

  it('carries Import, XLSX, CSV, Print and the Deleted Entries tab', async () => {
    const { wrapper, api } = await mountPage()
    await pickContext(wrapper)

    for (const label of ['Import', 'XLSX', 'CSV', 'Print']) {
      expect(buttonByLabel(wrapper, label), label).toBeTruthy()
    }

    await buttonByLabel(wrapper, 'CSV')?.trigger('click')
    await flushPromises()
    expect(api.download).toHaveBeenCalledWith(expect.stringContaining('/daily-cost/entries/export?format=csv'))

    await findTab(wrapper, 'Deleted Entries')?.trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('/daily-cost/entries/deleted?well_id=1')
    expect(wrapper.text()).toContain('Deleted Entries (Trash)')
    wrapper.unmount()
  })

  it('renders the print sheet for the open day', async () => {
    const { wrapper } = await mountPage(savedDay())
    await pickContext(wrapper)
    const sheet = wrapper.find('[data-testid="daily-cost-print-sheet"]')
    expect(sheet.exists()).toBe(true)
    expect(sheet.text()).toContain('Daily Cost Sheet')
    expect(sheet.text()).toContain('WELL001/20260801')
    expect(sheet.text()).toContain('Directional Drilling')
    wrapper.unmount()
  })
})
