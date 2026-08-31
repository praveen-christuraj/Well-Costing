import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AfePrintSheet from '~/components/afe/AfePrintSheet.vue'
import type { AfeEstimate } from '~/types/afe'

/**
 * The printed AFE reads as a portrait two-pager:
 *
 *   page 1 — metadata, well configuration, then the summary: one row per
 *   service with its cost (never split section-wise / phase-wise), the
 *   consumable main categories with their totals, and Services +
 *   Consumables + Tangibles rolled into the Total AFE cost;
 *   page 2 — the list of tangibles to be used.
 */

function component(sectionId: number | null, label: string | null) {
  return {
    category: 'Operation',
    description: `Operation — 5.5 day(s) @ 1000.00`,
    quantity: '5.50',
    rate: '1000.00',
    unit: 'days',
    amount: '5500.00',
    section_label: label,
    phase_label: null,
  }
}

const estimate: AfeEstimate = {
  afe: {
    id: 1,
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
    service_count: 1,
    consumable_count: 2,
    tangible_count: 1,
    estimated_total: '13700.00',
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
    total_depth: '3000',
    total_days: '9.50',
    sections: [
      {
        id: 21,
        section_id: 1,
        section_code: 'SEC1',
        section_name: 'Surface Section',
        from_depth: '0',
        to_depth: '1500',
        remarks: null,
        total_days: '5.50',
        phases: [{ id: 31, phase_id: 1, phase_code: 'PH1', phase_name: 'Drilling', days: '5.50', remarks: null }],
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
        phases: [{ id: 32, phase_id: 2, phase_code: 'PH2', phase_name: 'Casing', days: '4.00', remarks: null }],
      },
    ],
  },
  services: [
    {
      id: 1,
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
      rates: [],
      charge_lines: [],
      section_rates: [],
      estimate: {
        amount: '9500.00',
        warnings: [],
        // Split per section by the engine — the print shows one row anyway.
        components: [component(1, 'SEC1 — Surface Section'), component(2, 'SEC2 — Intermediate')],
      },
    },
  ],
  consumables: [
    {
      id: 2,
      item_kind: 'drill_bit',
      item_id: 7,
      item_code: 'DB-0001',
      item_name: 'Bit 12-1/4',
      quantity: '10',
      captured_rate: '120.00',
      override_rate: null,
      uom: null,
      currency: 'USD',
      section_id: 1,
      phase_id: 1,
      remarks: null,
      estimate: {
        amount: '1200.00',
        warnings: [],
        components: [{
          category: 'Consumption',
          description: 'Bit 12-1/4 — 10 unit @ 120.00',
          quantity: '10',
          rate: '120.00',
          unit: null,
          amount: '1200.00',
          section_label: 'SEC1 — Surface Section',
          phase_label: 'PH1 — Drilling',
        }],
      },
    },
    {
      id: 4,
      item_kind: 'mud_chemical',
      item_id: 0,
      item_code: 'LUMPSUM',
      item_name: 'Mud Chemicals',
      quantity: '1',
      captured_rate: '0',
      override_rate: '2000.00',
      uom: null,
      currency: null,
      section_id: 2,
      phase_id: null,
      remarks: null,
      estimate: {
        amount: '2000.00',
        warnings: [],
        components: [{
          category: 'Lump sum',
          description: 'Mud Chemicals — lump sum',
          quantity: '1',
          rate: '2000.00',
          unit: null,
          amount: '2000.00',
          section_label: 'SEC2 — Intermediate',
          phase_label: null,
        }],
      },
    },
  ],
  tangibles: [
    {
      id: 3,
      tangible_id: 9,
      tangible_code: 'TNG-0001',
      tangible_name: 'Casing 9-5/8',
      quantity: '2',
      captured_rate: '500.00',
      override_rate: null,
      uom: 'm',
      currency: 'USD',
      remarks: null,
      estimate: {
        amount: '1000.00',
        warnings: [],
        components: [{
          category: 'Captured rate',
          description: 'Casing 9-5/8 — 2 m @ 500.00',
          quantity: '2',
          rate: '500.00',
          unit: 'm',
          amount: '1000.00',
          section_label: null,
          phase_label: null,
        }],
      },
    },
  ],
  summary: [
    { group: 'Services', amount: '9500.00', line_count: 1 },
    { group: 'Consumables', amount: '3200.00', line_count: 2 },
    { group: 'Tangibles', amount: '1000.00', line_count: 1 },
  ],
  by_section: [
    { section_id: 1, section_label: 'SEC1 — Surface Section', planned_days: '5.50', amount: '6700.00' },
    { section_id: 2, section_label: 'SEC2 — Intermediate', planned_days: '4.00', amount: '4800.00' },
  ],
  grand_total: '13700.00',
  warnings: [],
}

function sheet() {
  return mount(AfePrintSheet, { props: { estimate, printedAt: '30/08/2026, 11:00' } })
}

describe('AfePrintSheet', () => {
  it('prints the sections in the specified order', () => {
    const text = sheet().text()
    const titles = [
      'Well configuration',
      'AFE cost estimate summary',
      'Services total',
      'Consumables total',
      'Total AFE cost',
      'Tangibles to be used',
    ]
    let previous = -1
    for (const title of titles) {
      const at = text.indexOf(title)
      expect(at, `"${title}" must be printed`).toBeGreaterThan(-1)
      expect(at, `"${title}" must come after the previous section`).toBeGreaterThan(previous)
      previous = at
    }
  })

  it('shows every configured section with its phases and planned days', () => {
    const wrapper = sheet()
    const text = wrapper.text()
    expect(text).toContain('SEC1 — Surface Section')
    expect(text).toContain('SEC2 — Intermediate')
    expect(text).toContain('PH2 — Casing')
    expect(text).toContain('4')
  })

  it('prints one row per service with its total cost, not per-section splits', () => {
    const wrapper = sheet()
    const servicesTable = wrapper.find('.afe-print__services')
    expect(servicesTable.exists()).toBe(true)
    const rows = servicesTable.findAll('tbody tr')
    expect(rows).toHaveLength(1)
    expect(rows[0]!.text()).toContain('SVC-0001')
    expect(rows[0]!.text()).toContain('Directional Drilling')
    expect(rows[0]!.text()).toContain('9,500.00')
    expect(servicesTable.text()).toContain('Services total')
  })

  it('rolls consumables up to their main category', () => {
    const wrapper = sheet()
    const categoriesTable = wrapper.find('.afe-print__categories')
    expect(categoriesTable.exists()).toBe(true)
    const text = categoriesTable.text()
    expect(text).toContain('Drill Bits')
    expect(text).toContain('Mud Chemicals')
    expect(text).toContain('1,200.00')
    expect(text).toContain('2,000.00')
    expect(text).toContain('Consumables total')
    expect(text).toContain('3,200.00')
    // Section-wise costs are not printed for consumables.
    expect(text).not.toContain('SEC1 — Surface Section')
  })

  it('adds the three groups into the Total AFE cost', () => {
    const totals = sheet().find('.afe-print__totals')
    expect(totals.exists()).toBe(true)
    const text = totals.text()
    expect(text).toContain('Services total')
    expect(text).toContain('Consumables total')
    expect(text).toContain('Tangibles total')
    expect(text).toContain('Total AFE cost')
    expect(text).toContain('13,700.00')
  })

  it('lists the tangibles to be used on their own page', () => {
    const wrapper = sheet()
    const page2 = wrapper.find('.afe-print__page2')
    expect(page2.exists()).toBe(true)
    expect(page2.classes()).toContain('afe-print__page2')
    const text = page2.text()
    expect(text).toContain('Tangibles to be used')
    expect(text).toContain('TNG-0001')
    expect(text).toContain('Casing 9-5/8')
    expect(text).toContain('1,000.00')
  })
})
