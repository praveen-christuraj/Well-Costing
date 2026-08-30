import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AfePrintSheet from '~/components/afe/AfePrintSheet.vue'
import type { AfeEstimate } from '~/types/afe'

/**
 * The printed AFE must read in the specified order — metadata, well
 * configuration, the AFE cost estimate summary, then services, consumables
 * and tangibles — and every priced service row has to show the section it was
 * charged against (a well-wide daily service is split per section).
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
    consumable_count: 1,
    tangible_count: 1,
    estimated_total: '12700.00',
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
    { group: 'Consumables', amount: '1200.00', line_count: 1 },
    { group: 'Tangibles', amount: '1000.00', line_count: 1 },
  ],
  by_section: [
    { section_id: 1, section_label: 'SEC1 — Surface Section', planned_days: '5.50', amount: '6700.00' },
    { section_id: 2, section_label: 'SEC2 — Intermediate', planned_days: '4.00', amount: '2800.00' },
    { section_id: null, section_label: 'Well-wide (no section)', planned_days: '0', amount: '1200.00' },
  ],
  grand_total: '11700.00',
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
      'Services',
      'Consumables',
      'Tangibles',
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

  it('shows the section each priced service row was charged against', () => {
    // The daily service is split per section; both rows must name theirs.
    const wrapper = sheet()
    expect(wrapper.text()).toContain('SEC1 — Surface Section')
    expect(wrapper.text()).toContain('SEC2 — Intermediate')
    const rows = wrapper.findAll('tbody tr')
    const serviceRows = rows.filter(row => row.text().includes('Operation'))
    expect(serviceRows).toHaveLength(2)
    expect(serviceRows[0]!.text()).toContain('SEC1 — Surface Section')
    expect(serviceRows[1]!.text()).toContain('SEC2 — Intermediate')
  })

  it('prints the summary with the grand total and the per-section rollup', () => {
    const text = sheet().text()
    expect(text).toContain('Total AFE cost estimate')
    expect(text).toContain('11,700.00')
    expect(text).toContain('Well-wide (no section)')
  })
})
