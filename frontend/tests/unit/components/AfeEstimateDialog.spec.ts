import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CHARGE_CATEGORIES } from '~/types/afe'

/**
 * Component test for the AFE Cost Estimation dialog: the pickers pull from the
 * master data passed in by the page, the service row carries all eight constant
 * charge categories, the payload sent to the API is shaped for the backend, and
 * the live preview keeps the totals coming from the server engine.
 */

const estimate = {
  afe: {
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
    rig_display: 'RIG001 - Drilling Rig Alpha',
    well_display: 'WELL001 - Exploratory 1',
    service_count: 0,
    consumable_count: 0,
    tangible_count: 0,
    estimated_total: '0',
  },
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
      {
        id: 22,
        section_id: 2,
        section_code: 'SEC2',
        section_name: 'Intermediate',
        from_depth: '1500',
        to_depth: '3000',
        remarks: null,
        total_days: '4.00',
        phases: [{ id: 33, phase_id: 1, phase_code: 'PH1', phase_name: 'Drilling', days: '4.00', remarks: null }],
      },
    ],
  },
  services: [],
  consumables: [],
  tangibles: [],
  summary: [],
  by_section: [],
  grand_total: '0',
  warnings: [],
}

const previewResponse = {
  services: [{ amount: '13000.00', components: [], warnings: [] }],
  consumables: [],
  tangibles: [],
  summary: [{ group: 'Services', amount: '13000.00', line_count: 1 }],
  by_section: [{ section_id: null, section_label: 'Well-wide (no section)', planned_days: '0', amount: '13000.00' }],
  grand_total: '13000.00',
  warnings: [],
}

const services = [
  { id: 5, service_code: 'SVC-0001', service_name: 'Directional Drilling', provider_type: 'Inhouse' },
  { id: 6, service_code: 'SVC-0002', service_name: 'Cementing', provider_type: '3rd Party' },
]
const consumables = [
  { id: 7, code: 'MC-0001', name: 'Bentonite', rate: 120, uom: 'Sack', currency: 'USD', kind: 'mud_chemical' as const, detail: 'Mud Chemical · Sack', description: 'Viscosifier for drilling mud' },
  {
    id: 8,
    code: 'DB-0001',
    name: 'Bit 12-1/4 PDC',
    rate: 1200,
    uom: null,
    currency: 'USD',
    kind: 'drill_bit' as const,
    detail: 'Drill Bit · PDC',
    manufacturer: 'NOV',
    itemType: 'PDC',
    size: '12-1/4',
    iadcCode: 'M123',
    modelNo: 'Model123',
    description: 'Six-blade PDC bit for interbedded formations',
  },
]
const tangibles = [
  {
    id: 9,
    code: 'TNG-0001',
    name: 'Casing 9-5/8',
    rate: 500,
    uom: 'm',
    currency: 'USD',
    detail: 'Drilling · Casing',
    manufacturer: 'Tenaris',
    category: 'Casing',
    subcategory: 'Surface Casing',
    description: '9-5/8 53.5# P110 casing string',
  },
]

type ApiMock = Record<'get' | 'post' | 'put' | 'delete', ReturnType<typeof vi.fn>>

function makeApi(): ApiMock {
  return {
    get: vi.fn().mockResolvedValue(estimate),
    post: vi.fn((path: string) =>
      path.endsWith('/preview') ? Promise.resolve(previewResponse) : Promise.resolve({}),
    ),
    put: vi.fn().mockResolvedValue(estimate),
    delete: vi.fn().mockResolvedValue(undefined),
  }
}

async function mountDialog() {
  vi.resetModules()
  const api = makeApi()
  vi.stubGlobal('useApi', () => api)

  const component = (await import('~/components/afe/AfeEstimateDialog.vue')).default
  const wrapper = mount(component, {
    props: { visible: true, afeId: 10, services, consumables, tangibles },
    global: {
      stubs: {
        // Render a dialog's contents inline, but only while it is visible.
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
        },
      },
    },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, api }
}

function findButton(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find(button => button.text().includes(label))
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('AFE Cost Estimation dialog', () => {
  it('loads the stored estimate for the selected AFE', async () => {
    const { wrapper, api } = await mountDialog()
    expect(api.get).toHaveBeenCalledWith('/afe/estimates/10')
    // The header text is a Dialog prop (not rendered by the stub); the body
    // proves the stored estimate was loaded.
    expect(wrapper.text()).toContain('Surface section drilling')
    expect(wrapper.text()).toContain('RIG001 - Drilling Rig Alpha · WELL001 - Exploratory 1')
    wrapper.unmount()
  })

  it('adds a picked service with the eight constant charge categories', async () => {
    const { wrapper } = await mountDialog()
    await findButton(wrapper, 'Add service')?.trigger('click')
    await flushPromises()

    const pickerRows = wrapper.findAll('.afe-picker__row')
    expect(pickerRows).toHaveLength(2)
    await pickerRows[0]?.find('input').setValue(true)
    await findButton(wrapper, 'Add 1')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Directional Drilling')

    // The rate card sits in the row expansion.
    await wrapper.find('tbody button[aria-expanded]').trigger('click')
    await flushPromises()
    // Every charge category is available on the row, whether or not it has a rate.
    for (const category of CHARGE_CATEGORIES) {
      expect(wrapper.text()).toContain(category)
    }
    wrapper.unmount()
  })

  it('filters the picker and adds consumables and tangibles from the master data', async () => {
    const { wrapper } = await mountDialog()

    await findButton(wrapper, 'Consumables')?.trigger('click')
    await flushPromises()
    await findButton(wrapper, 'Add consumable')?.trigger('click')
    await flushPromises()
    await wrapper.find('.afe-picker__search input').setValue('nothing matches this')
    await flushPromises()
    expect(wrapper.findAll('.afe-picker__row')).toHaveLength(0)

    await wrapper.find('.afe-picker__search input').setValue('bentonite')
    await flushPromises()
    expect(wrapper.findAll('.afe-picker__row')).toHaveLength(1)
    await wrapper.find('.afe-picker__row input').setValue(true)
    await findButton(wrapper, 'Add 1')?.trigger('click')
    await flushPromises()

    await findButton(wrapper, 'Tangibles')?.trigger('click')
    await flushPromises()
    await findButton(wrapper, 'Add tangible')?.trigger('click')
    await flushPromises()
    await wrapper.find('.afe-picker__row input').setValue(true)
    await findButton(wrapper, 'Add 1')?.trigger('click')
    await flushPromises()

    // The sub-tab badges show both additions; switch back to see the consumable.
    expect(wrapper.text()).toContain('Consumables 1')
    expect(wrapper.text()).toContain('Tangibles 1')
    expect(wrapper.text()).toContain('Casing 9-5/8')

    await findButton(wrapper, 'Consumables')?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Bentonite')
    expect(wrapper.text()).toContain('MC-0001')
    wrapper.unmount()
  })

  it('sends the payload the backend expects and refreshes the totals', async () => {
    const { wrapper, api } = await mountDialog()

    await findButton(wrapper, 'Add service')?.trigger('click')
    await flushPromises()
    await wrapper.find('.afe-picker__row input').setValue(true)
    await findButton(wrapper, 'Add 1')?.trigger('click')
    await flushPromises()

    await findButton(wrapper, 'Save')?.trigger('click')
    await flushPromises()

    const [path, payload] = api.put.mock.calls[0] as [string, any]
    expect(path).toBe('/afe/estimates/10')
    expect(payload.services).toHaveLength(1)
    expect(payload.services[0]).toMatchObject({
      service_id: 5,
      charging_basis: 'Daily Rate',
      section_id: null,
      phase_id: null,
    })
    // Unpriced categories are not sent, and the day-based lists start empty.
    expect(payload.services[0].rates).toEqual([])
    expect(payload.services[0].charge_lines).toEqual([])
    expect(payload.services[0].section_rates).toEqual([])
    expect(payload.consumables).toEqual([])
    expect(payload.tangibles).toEqual([])

    // Saving cancels the pending preview and the reload after it skips the
    // redundant request (the loaded estimate already carries the totals), so
    // the live preview is asserted from a *new* edit: add the service again,
    // type a rate and wait out the debounce. It goes through the same engine
    // as Save.
    await findButton(wrapper, 'Add service')?.trigger('click')
    await flushPromises()
    await wrapper.find('.afe-picker__row input').setValue(true)
    await findButton(wrapper, 'Add 1')?.trigger('click')
    await flushPromises()
    await wrapper.find('tbody button[aria-expanded]').trigger('click')
    await flushPromises()
    const rateInput = wrapper.find('input[inputmode="decimal"]')
    await rateInput.setValue('1000')
    await new Promise(resolve => setTimeout(resolve, 800))
    await flushPromises()
    const previewCalls = api.post.mock.calls.filter(call => String(call[0]).endsWith('/preview'))
    expect(previewCalls.length).toBeGreaterThan(0)
    expect((previewCalls.at(-1) as unknown[])?.[1]).toMatchObject({
      services: [expect.objectContaining({ service_id: 5 })],
    })
    wrapper.unmount()
  })

  it('matches the picker rows by any catalogue keyword', async () => {
    const { wrapper } = await mountDialog()

    // Tangibles: manufacturer, description and code fragments all match —
    // and several tokens can be combined (advanced search semantics).
    await findButton(wrapper, 'Tangibles')?.trigger('click')
    await flushPromises()
    await findButton(wrapper, 'Add tangible')?.trigger('click')
    await flushPromises()

    const search = wrapper.find('.afe-picker__search input')
    await search.setValue('tenaris')
    await flushPromises()
    expect(wrapper.findAll('.afe-picker__row')).toHaveLength(1)
    expect(wrapper.text()).toContain('Tenaris · Casing · Surface Casing')
    expect(wrapper.text()).toContain('9-5/8 53.5# P110 casing string')

    await search.setValue('p110 casing')
    await flushPromises()
    expect(wrapper.findAll('.afe-picker__row')).toHaveLength(1)

    await search.setValue('tenaris drill bit')
    await flushPromises()
    expect(wrapper.findAll('.afe-picker__row')).toHaveLength(0)

    // Consumables: a drill bit matches on its make, type and description too.
    await findButton(wrapper, 'Cancel')?.trigger('click')
    await findButton(wrapper, 'Consumables')?.trigger('click')
    await flushPromises()
    await findButton(wrapper, 'Add consumable')?.trigger('click')
    await flushPromises()
    await wrapper.find('.afe-picker__search input').setValue('interbedded')
    await flushPromises()
    expect(wrapper.findAll('.afe-picker__row')).toHaveLength(1)
    expect(wrapper.text()).toContain('NOV')

    await wrapper.find('.afe-picker__row input').setValue(true)
    await findButton(wrapper, 'Add 1')?.trigger('click')
    await flushPromises()
    // The picked bit row shows its identity: code + name, make, type, size.
    expect(wrapper.text()).toContain('DB-0001')
    expect(wrapper.text()).toContain('Bit 12-1/4 PDC')
    wrapper.unmount()
  })

  it('keeps a submitted AFE read-only and offers the approval', async () => {
    const submitted = { ...estimate, afe: { ...estimate.afe, status: 'submitted' as const } }
    vi.resetModules()
    const api = makeApi()
    api.get.mockResolvedValue(submitted)
    vi.stubGlobal('useApi', () => api)

    const component = (await import('~/components/afe/AfeEstimateDialog.vue')).default
    const wrapper = mount(component, {
      props: { visible: true, afeId: 10, services, consumables, tangibles },
      global: { stubs: { Dialog: { template: '<div><slot /><slot name="footer" /></div>' } } },
      attachTo: document.body,
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Submitted')
    expect(wrapper.text()).toContain('reopen it as Draft to edit')
    expect(findButton(wrapper, 'Save')?.attributes('disabled')).toBeDefined()
    expect(findButton(wrapper, 'Approve')).toBeTruthy()

    vi.spyOn(window, 'prompt').mockReturnValue('budget released')
    await findButton(wrapper, 'Approve')?.trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/afe/estimates/10/status', {
      action: 'approve',
      remarks: 'budget released',
    })
    wrapper.unmount()
  })
})
