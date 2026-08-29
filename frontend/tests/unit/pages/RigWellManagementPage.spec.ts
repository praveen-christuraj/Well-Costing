import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

/**
 * Page-level test for Rig & Well Management, focused on the Well Configuration
 * tab: the per-row Print button prints one well's saved configuration (draft or
 * configured) while the toolbar Print button keeps printing the whole list.
 */

const rigs = [
  { id: 1, rig_code: 'RIG001', rig_name: 'Drilling Rig Alpha', display_name: 'RIG001 - Drilling Rig Alpha' },
]

const wells = [
  {
    id: 1,
    rig_id: 1,
    well_code: 'WELL001',
    well_name: 'Exploratory 1',
    well_location: 'Block 12',
    block: 'Block A',
    objective: 'Appraisal',
    status: 'active',
    config_status: 'configured',
    depth_unit: 'm',
    rig_code: 'RIG001',
    rig_name: 'Drilling Rig Alpha',
    rig_display: 'RIG001 - Drilling Rig Alpha',
    total_depth: '1500',
    total_days: '8.00',
    section_count: 1,
  },
  {
    id: 2,
    rig_id: 1,
    well_code: 'WELL002',
    well_name: 'Exploratory 2',
    well_location: 'Block 13',
    block: 'Block A',
    objective: 'Appraisal',
    status: 'active',
    config_status: 'draft',
    depth_unit: 'm',
    rig_code: 'RIG001',
    rig_name: 'Drilling Rig Alpha',
    rig_display: 'RIG001 - Drilling Rig Alpha',
    total_depth: null,
    total_days: '0',
    section_count: 0,
  },
]

const configuration = {
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
      id: 11,
      section_id: 1,
      section_code: 'SEC1',
      section_name: 'Surface Section',
      from_depth: '0',
      to_depth: '1500',
      remarks: 'surface',
      total_days: '8.00',
      phases: [
        { id: 21, phase_id: 1, phase_code: 'PH1', phase_name: 'Drilling', days: '5.50', remarks: 'spud' },
        { id: 22, phase_id: 2, phase_code: 'PH2', phase_name: 'Casing', days: '2.50', remarks: null },
      ],
    },
  ],
}

type ApiMock = Record<'get' | 'post' | 'put' | 'delete' | 'download', ReturnType<typeof vi.fn>>

function makeApi(): ApiMock {
  return {
    get: vi.fn((path: string) => {
      if (path === '/rig-well/rigs/dropdown') return Promise.resolve(rigs)
      if (path === '/catalogue/configs/block') return Promise.resolve([{ id: 1, value: 'Block A' }])
      if (path === '/rig-well/wells') return Promise.resolve(wells)
      if (path === '/rig-well/wells/1/configuration') return Promise.resolve(configuration)
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

  const component = (await import('~/pages/rig-well-management/index.vue')).default
  const wrapper = mount(component, { attachTo: document.body })
  await flushPromises()
  return { wrapper, api }
}

function findTab(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.tabs__item').find(tab => tab.text().includes(label))
}

function rowButtons(wrapper: ReturnType<typeof mount>, wellCode: string) {
  const row = wrapper.findAll('tbody tr').find(candidate => candidate.text().includes(wellCode))
  return row ? row.findAll('button') : []
}

function findRowButton(wrapper: ReturnType<typeof mount>, wellCode: string, label: string) {
  return rowButtons(wrapper, wellCode).find(button => button.text().includes(label))
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('Rig & Well Management — Well Configuration printing', () => {
  it('renders the four navigation tabs as the shared tab strip', async () => {
    const { wrapper } = await mountPage()
    const labels = wrapper.findAll('.tabs__item').map(tab => tab.text().trim())
    expect(labels).toEqual(['Rig Management', 'Well Management', 'Well Configuration', 'Deleted Entries'])
    expect(findTab(wrapper, 'Deleted Entries')?.classes()).toContain('tabs__item--danger')
    wrapper.unmount()
  })

  it('prints a single well configuration from its row', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { wrapper, api } = await mountPage()

    await findTab(wrapper, 'Well Configuration')?.trigger('click')
    await flushPromises()

    const printButton = findRowButton(wrapper, 'WELL001', 'Print')
    expect(printButton).toBeTruthy()
    await printButton?.trigger('click')
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('/rig-well/wells/1/configuration')
    expect(print).toHaveBeenCalledTimes(1)

    // The single-well sheet replaces the list sheet while printing.
    const sheet = wrapper.findAll('.print-sheet')
    expect(sheet).toHaveLength(1)
    expect(sheet[0]?.text()).toContain('Well Configuration — WELL001')
    expect(sheet[0]?.text()).toContain('SEC1 — Surface Section')
    expect(sheet[0]?.text()).toContain('PH1 — Drilling')
    expect(sheet[0]?.text()).toContain('PH2 — Casing')
    expect(sheet[0]?.text()).toContain('1500 m')
    // The list sheet (2 wells) is not part of the print output.
    expect(sheet[0]?.text()).not.toContain('WELL002')
    wrapper.unmount()
  })

  it('clears the single-well sheet once printing finishes', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { wrapper } = await mountPage()

    await findTab(wrapper, 'Well Configuration')?.trigger('click')
    await flushPromises()
    await findRowButton(wrapper, 'WELL001', 'Print')?.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.print-sheet')[0]?.text()).toContain('WELL001')

    window.dispatchEvent(new Event('afterprint'))
    await flushPromises()

    const sheet = wrapper.findAll('.print-sheet')[0]
    expect(sheet?.text()).toContain('2 well(s)')
    expect(print).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('disables the row print button when nothing has been configured yet', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { wrapper, api } = await mountPage()

    await findTab(wrapper, 'Well Configuration')?.trigger('click')
    await flushPromises()

    const printButton = findRowButton(wrapper, 'WELL002', 'Print')
    expect(printButton?.attributes('disabled')).toBeDefined()
    await printButton?.trigger('click')
    await flushPromises()

    expect(api.get).not.toHaveBeenCalledWith('/rig-well/wells/2/configuration')
    expect(print).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
